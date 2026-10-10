"""ChronoTrace Chunking Engine.

Groups sustained MAIN events (dwell >= 10s) and their associated micro-behavior
snapshots into coherent cognitive activity chunks. Evaluates boundary conditions
(B1: IDLE_GAP, B2: ANCHOR_OPENED, B3: CATEGORY_SHIFT, B4: MAX_DURATION) in strict
priority order.
"""

from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
import logging
from typing import Any, Callable, Dict, List, Optional
import sys
from pathlib import Path

# Ensure root directory is on Python path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from collector.enricher import is_anchor
from config import CATEGORY_SHIFT_S, IDLE_GAP_S, MAX_CHUNK_DURATION_S

logger = logging.getLogger("chronotrace.chunker")


def _parse_ts(ts: Any) -> datetime:
    """Safely parse ISO string, timestamp number, or datetime object into UTC datetime."""
    if isinstance(ts, datetime):
        return ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)
    if isinstance(ts, (int, float)):
        return datetime.fromtimestamp(ts, tz=timezone.utc)
    if isinstance(ts, str):
        try:
            # Handle ISO string with potential 'Z' suffix
            clean_str = ts.replace("Z", "+00:00")
            dt = datetime.fromisoformat(clean_str)
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except Exception:
            pass
    return datetime.now(timezone.utc)


@dataclass
class Chunk:
    """Represents a bounded window of continuous focused activity.

    Attributes:
        events: List of sustained main-stream event dictionaries (dwell >= 10s).
        micro_blocks: List of serialized micro-behavior snapshots paired with main events.
        start_ts: Timestamp when the chunk began.
        end_ts: Timestamp when the chunk closed.
        anchor_opened: True if an anchor application was initiated/focused during this chunk.
        anchor_closed: True if user navigated away from an anchor application.
        close_reason: Boundary trigger that closed this chunk (e.g. IDLE_GAP, MAX_DURATION).
    """

    events: List[Dict[str, Any]] = field(default_factory=list)
    micro_blocks: List[Dict[str, Any]] = field(default_factory=list)
    start_ts: Optional[datetime] = None
    end_ts: Optional[datetime] = None
    anchor_opened: bool = False
    anchor_closed: bool = False
    close_reason: str = ""

    def add(self, event: Dict[str, Any], micro: Any) -> None:
        """Append a main event and its accompanying micro-behavior block to the chunk.

        Args:
            event: Main stream window event dictionary.
            micro: MicroCounters instance or serialized dictionary.
        """
        event_ts = _parse_ts(event.get("timestamp"))

        if not self.events:
            self.start_ts = event_ts

        self.end_ts = event_ts
        self.events.append(event)

        # Store micro dictionary snapshot
        if hasattr(micro, "to_dict"):
            self.micro_blocks.append(micro.to_dict())
        elif isinstance(micro, dict):
            self.micro_blocks.append(micro)
        else:
            self.micro_blocks.append({})

        # Track anchor activity state
        app_name = event.get("app_name", "")
        if is_anchor(app_name):
            self.anchor_opened = True

    def duration_s(self) -> float:
        """Calculate total elapsed chunk duration in seconds.

        Returns:
            Duration in seconds computed from cumulative dwell times or timestamps.
        """
        if not self.events:
            return 0.0

        # Dwell time sum in seconds
        dwell_sum = sum(float(e.get("dwell_ms", 0)) for e in self.events) / 1000.0

        if self.start_ts and self.end_ts:
            ts_diff = (self.end_ts - self.start_ts).total_seconds()
            return max(dwell_sum, ts_diff)

        return dwell_sum

    def last_category(self) -> Optional[str]:
        """Return the category of the most recent event in this chunk."""
        if not self.events:
            return None
        return self.events[-1].get("category")

    def dominant_app(self) -> Optional[str]:
        """Determine the application where the most time was spent by dwell_ms.

        Returns:
            App name string with highest dwell time, or None if empty.
        """
        if not self.events:
            return None

        app_dwell: Dict[str, int] = {}
        for ev in self.events:
            app = ev.get("app_name", "Unknown")
            app_dwell[app] = app_dwell.get(app, 0) + int(ev.get("dwell_ms", 0))

        return max(app_dwell.items(), key=lambda item: item[1])[0]


class Chunker:
    """Applies boundary detection to segment incoming events into discrete chunks."""

    def __init__(self, on_chunk_complete: Optional[Callable[[Chunk], None]] = None) -> None:
        """Initialize Chunker with completion callback.

        Args:
            on_chunk_complete: Callback invoked when a chunk is completed and closed.
        """
        self.on_chunk_complete = on_chunk_complete
        self.current_chunk: Chunk = Chunk()
        self._last_event_end_time: Optional[datetime] = None

    def add_event(self, event: Dict[str, Any], micro: Any) -> None:
        """Evaluate boundary triggers (B1-B4) and add event to current or new chunk.

        Boundary priority order:
            B1. IDLE_GAP: Inactivity gap between events > IDLE_GAP_S (120s)
            B2. ANCHOR_OPENED: An anchor application is opened when chunk had none
            B3. CATEGORY_SHIFT: Sustained category change >= CATEGORY_SHIFT_S (30s)
            B4. MAX_DURATION: Current chunk duration >= MAX_CHUNK_DURATION_S (1200s)

        Args:
            event: Sustained event dictionary with app_name, dwell_ms, etc.
            micro: Micro behavior snapshot associated with this transition.
        """
        event_ts = _parse_ts(event.get("timestamp"))
        dwell_ms = int(event.get("dwell_ms", 0))
        event_dwell_s = dwell_ms / 1000.0
        app_name = event.get("app_name", "")
        category = event.get("category", "")

        # Only evaluate boundaries if current chunk already contains events
        if self.current_chunk.events:
            boundary_reason: Optional[str] = None

            # B1: IDLE_GAP
            if self._last_event_end_time:
                idle_gap = (event_ts - self._last_event_end_time).total_seconds()
                if idle_gap > IDLE_GAP_S:
                    boundary_reason = "IDLE_GAP"

            # B2: ANCHOR_OPENED
            if not boundary_reason:
                # If newly opened app is an anchor and previous events in chunk were non-anchor
                if is_anchor(app_name) and not self.current_chunk.anchor_opened:
                    boundary_reason = "ANCHOR_OPENED"

            # B3: CATEGORY_SHIFT
            if not boundary_reason:
                last_cat = self.current_chunk.last_category()
                if last_cat and category != last_cat and event_dwell_s >= CATEGORY_SHIFT_S:
                    boundary_reason = "CATEGORY_SHIFT"

            # B4: MAX_DURATION
            if not boundary_reason:
                if self.current_chunk.duration_s() + event_dwell_s >= MAX_CHUNK_DURATION_S:
                    boundary_reason = "MAX_DURATION"

            # If any boundary condition met, close current chunk and begin new chunk
            if boundary_reason:
                self._close_current_chunk(reason=boundary_reason)

        # Add event to current (or newly refreshed) chunk
        self.current_chunk.add(event, micro)
        self._last_event_end_time = datetime.fromtimestamp(
            event_ts.timestamp() + event_dwell_s, tz=timezone.utc
        )

    def force_close(self, reason: str = "FORCED") -> Optional[Chunk]:
        """Force completion of the current chunk, e.g. on laptop sleep or idle timeout.

        Args:
            reason: Identifier for close trigger (default: "FORCED").

        Returns:
            The closed Chunk instance, or None if current chunk was empty.
        """
        if self.current_chunk and self.current_chunk.events:
            return self._close_current_chunk(reason=reason)
        return None

    def _close_current_chunk(self, reason: str) -> Chunk:
        """Finalize and dispatch the current chunk to on_chunk_complete callback."""
        closed = self.current_chunk
        closed.close_reason = reason

        # Check if anchor was closed before exiting
        if closed.events:
            last_app = closed.events[-1].get("app_name", "")
            if closed.anchor_opened and not is_anchor(last_app):
                closed.anchor_closed = True

        # Dispatch completed chunk
        if self.on_chunk_complete:
            try:
                self.on_chunk_complete(closed)
            except Exception as e:
                logger.error(f"Error in on_chunk_complete callback: {e}", exc_info=True)

        # Re-initialize clean chunk
        self.current_chunk = Chunk()
        return closed
