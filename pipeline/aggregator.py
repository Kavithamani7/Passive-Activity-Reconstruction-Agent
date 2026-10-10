"""ChronoTrace Chunk Aggregator.

Transforms completed raw chunks into a compact (~150 token) structured JSON summary.
Computes anchor persistence, micro-behavior metrics (restlessness, tab flickers),
keystroke rates, dominant category by dwell time, and triggers asynchronous LLM
intent classification.
"""

from collections import Counter
from datetime import datetime, timezone
import logging
import threading
from typing import Any, Dict, List, Optional
import sys
from pathlib import Path

# Ensure root directory is on Python path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from collector.enricher import is_anchor
from pipeline.chunker import Chunk

logger = logging.getLogger("chronotrace.aggregator")


class Aggregator:
    """Aggregates chunk events and behavioral micro-counters into a standardized payload."""

    def __init__(self, llm_engine: Optional[Any] = None) -> None:
        """Initialize the Aggregator.

        Args:
            llm_engine: Downstream LLM engine providing classify_async(summary) method.
        """
        self.llm_engine = llm_engine
        self._chunk_counter: int = 0
        self._counter_lock = threading.Lock()

    def set_llm_engine(self, llm_engine: Any) -> None:
        """Attach or update the downstream LLM engine."""
        self.llm_engine = llm_engine

    def _generate_chunk_id(self, start_dt: datetime) -> str:
        """Generate chunk identifier in format: YYYYMMDD_HHMMSS_counter."""
        with self._counter_lock:
            self._chunk_counter += 1
            counter_val = self._chunk_counter

        date_str = start_dt.strftime("%Y%m%d")
        time_str = start_dt.strftime("%H%M%S")
        return f"{date_str}_{time_str}_{counter_val:03d}"

    def process(self, chunk: Chunk) -> Dict[str, Any]:
        """Aggregate chunk data into a structured summary dictionary.

        Args:
            chunk: Finalized Chunk instance.

        Returns:
            Dictionary containing all aggregated metrics and event summaries.
        """
        events = chunk.events
        micro_blocks = chunk.micro_blocks

        # Default fallback timestamps
        start_dt = chunk.start_ts or datetime.now(timezone.utc)
        end_dt = chunk.end_ts or start_dt

        chunk_id = self._generate_chunk_id(start_dt)
        duration_s = round(chunk.duration_s(), 1)
        start_time_str = start_dt.strftime("%H:%M:%S")
        end_time_str = end_dt.strftime("%H:%M:%S")
        closed_by = chunk.close_reason or "MANUAL"

        # 1. Main events projection
        main_events: List[Dict[str, Any]] = []
        total_keys = 0
        category_dwell: Dict[str, float] = {}
        anchor_dwell: Dict[str, float] = {}
        categories_present_set = set()

        for ev in events:
            app = ev.get("app_name", "Unknown")
            title = ev.get("window_title", "")
            dwell_ms = int(ev.get("dwell_ms", 0))
            dwell_s = round(dwell_ms / 1000.0, 1)
            keys = int(ev.get("keyboard_events", 0))
            cat = ev.get("category", "Utility")

            total_keys += keys
            categories_present_set.add(cat)
            category_dwell[cat] = category_dwell.get(cat, 0.0) + dwell_s

            if is_anchor(app):
                anchor_dwell[app] = anchor_dwell.get(app, 0.0) + dwell_s

            main_events.append({
                "app": app,
                "title": title,
                "dwell_s": dwell_s,
                "keys": keys,
            })

        # 2. Anchor metrics & returned_to_anchor detection
        anchor_app: Optional[str] = None
        anchor_held_s: float = 0.0
        returned_to_anchor: bool = False

        if anchor_dwell:
            # Primary anchor is the anchor app with greatest dwell time
            anchor_app, anchor_held_s = max(anchor_dwell.items(), key=lambda x: x[1])
            anchor_held_s = round(anchor_held_s, 1)

            # Determine if user left primary anchor and returned to it
            seen_anchor = False
            left_anchor = False
            for ev in events:
                curr_app = ev.get("app_name", "")
                if curr_app == anchor_app:
                    if left_anchor:
                        returned_to_anchor = True
                        break
                    seen_anchor = True
                else:
                    if seen_anchor:
                        left_anchor = True

        # 3. Keyboard typing velocity
        rate_per_min = 0.0
        if duration_s > 0:
            rate_per_min = round(total_keys / (duration_s / 60.0), 1)

        keyboard_stats = {
            "total_keys": total_keys,
            "rate_per_min": rate_per_min,
        }

        # 4. Micro-behavior aggregation across sub-threshold bursts
        total_rapid_switches = 0
        total_tab_flickers = 0
        total_micro_dwell_ms = 0
        total_micro_event_count = 0
        micro_patterns: List[str] = []
        unique_micro_apps_set = set()

        for block in micro_blocks:
            total_rapid_switches += int(block.get("rapid_switches", 0))
            total_tab_flickers += int(block.get("tab_flickers", 0))
            total_micro_dwell_ms += int(block.get("total_dwell_ms", 0))
            total_micro_event_count += int(block.get("events_count", len(block.get("events", []))))

            for app in block.get("unique_apps", []):
                unique_micro_apps_set.add(app)

            pattern = block.get("pattern")
            if pattern:
                micro_patterns.append(pattern)

        avg_micro_dwell_ms = 0.0
        if total_micro_event_count > 0:
            avg_micro_dwell_ms = round(total_micro_dwell_ms / total_micro_event_count, 1)

        # Dominant micro pattern
        dominant_pattern = "NORMAL"
        if micro_patterns:
            pattern_counts = Counter(micro_patterns)
            # Prioritize non-normal patterns if present
            non_normal = {k: v for k, v in pattern_counts.items() if k != "NORMAL"}
            if non_normal:
                dominant_pattern = max(non_normal.items(), key=lambda x: x[1])[0]
            else:
                dominant_pattern = "NORMAL"

        micro_behavior = {
            "total_rapid_switches": total_rapid_switches,
            "tab_flickers": total_tab_flickers,
            "avg_micro_dwell_ms": avg_micro_dwell_ms,
            "dominant_pattern": dominant_pattern,
            "unique_micro_apps": sorted(list(unique_micro_apps_set)),
        }

        # 5. Dominant category (weighted strictly by dwell time, not event count)
        dominant_category = "Utility"
        if category_dwell:
            dominant_category = max(category_dwell.items(), key=lambda x: x[1])[0]

        # 6. Copy-paste / rapid reference event detection
        # Counts transitions between documents/IDEs and browsers under 20s
        copy_paste_events = 0
        for i in range(len(events) - 1):
            curr_ev = events[i]
            next_ev = events[i + 1]
            if curr_ev.get("app_name") != next_ev.get("app_name"):
                dwell = next_ev.get("dwell_ms", 0)
                if dwell <= 20000 and next_ev.get("keyboard_events", 0) > 0:
                    copy_paste_events += 1

        # 7. Restless session start signal
        session_start_restless = False
        if micro_blocks and len(micro_blocks) > 0:
            first_pattern = micro_blocks[0].get("pattern", "")
            if first_pattern == "RESTLESS":
                session_start_restless = True

        # Assemble canonical summary payload
        summary: Dict[str, Any] = {
            "chunk_id": chunk_id,
            "duration_s": duration_s,
            "start_time": start_time_str,
            "end_time": end_time_str,
            "closed_by": closed_by,
            "main_events": main_events,
            "anchor_app": anchor_app,
            "anchor_held_s": anchor_held_s,
            "returned_to_anchor": returned_to_anchor,
            "keyboard": keyboard_stats,
            "micro_behavior": micro_behavior,
            "categories_present": sorted(list(categories_present_set)),
            "dominant_category": dominant_category,
            "copy_paste_events": copy_paste_events,
            "session_start_restless": session_start_restless,
        }

        # Asynchronously dispatch to LLM Intent Engine if configured
        if self.llm_engine is not None:
            self._dispatch_to_llm(summary)

        return summary

    def _dispatch_to_llm(self, summary: Dict[str, Any]) -> None:
        """Forward summary payload asynchronously to LLM classifier."""
        try:
            if hasattr(self.llm_engine, "classify_async"):
                self.llm_engine.classify_async(summary)
            elif hasattr(self.llm_engine, "classify"):
                threading.Thread(
                    target=self.llm_engine.classify,
                    args=(summary,),
                    name="ChronoTraceLLMClassify",
                    daemon=True,
                ).start()
        except Exception as e:
            logger.error(f"Error invoking LLM engine classification: {e}", exc_info=True)
