"""ChronoTrace Event Splitter.

Implements the second layer of the ChronoTrace pipeline:
Separates events by dwell time threshold (10,000ms).
Sub-10s events are aggregated into high-fidelity micro-behavior counters
(rapid switches, tab flickers, restlessness patterns).
Sustained events (>=10s) are dispatched to the chunker accompanied by the
accumulated micro-behavior context.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set
import copy
import sys
from pathlib import Path

# Ensure root directory is on Python path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import MICRO_THRESHOLD_MS


@dataclass
class MicroCounters:
    """Aggregates sub-threshold (<10s) micro-events to detect cognitive restlessness.

    Attributes:
        rapid_switches: Number of fast transitions between applications or windows.
        unique_apps: Set of distinct application names encountered during micro bursts.
        tab_flickers: Number of rapid switches occurring within the same browser/app (e.g. Chrome tab switching).
        total_dwell_ms: Cumulative dwell time spent in micro states in milliseconds.
        events: Historical list of raw micro-event dictionaries recorded in this window.
    """

    rapid_switches: int = 0
    unique_apps: Set[str] = field(default_factory=set)
    tab_flickers: int = 0
    total_dwell_ms: int = 0
    events: List[Dict[str, Any]] = field(default_factory=list)

    def add(self, event: Dict[str, Any]) -> None:
        """Incorporate a micro-event into the counters.

        Args:
            event: Window event dictionary with app_name, window_title, dwell_ms, etc.
        """
        app = event.get("app_name", "")
        dwell = int(event.get("dwell_ms", 0))

        # Check for tab flicker: same app as previous micro event but different window title
        if self.events:
            prev_event = self.events[-1]
            prev_app = prev_event.get("app_name", "")
            prev_title = prev_event.get("window_title", "")
            curr_title = event.get("window_title", "")

            if prev_app == app and prev_title != curr_title:
                self.tab_flickers += 1

        self.rapid_switches += 1
        if app:
            self.unique_apps.add(app)
        self.total_dwell_ms += dwell
        self.events.append(event)

    def avg_dwell_ms(self) -> float:
        """Calculate the average dwell time across recorded micro events.

        Returns:
            Average dwell time in milliseconds, or 0.0 if no events exist.
        """
        if not self.events:
            return 0.0
        return self.total_dwell_ms / len(self.events)

    def pattern(self) -> str:
        """Evaluate behavioral classification from accumulated micro signals.

        Rules:
            1. RESTLESS: rapid_switches >= 5 and avg_dwell < 3000ms
            2. TAB_HUNTING: tab_flickers >= 3
            3. SWITCHING: rapid_switches >= 3
            4. NORMAL: default baseline state

        Returns:
            Pattern label string: "RESTLESS", "TAB_HUNTING", "SWITCHING", or "NORMAL".
        """
        avg_dwell = self.avg_dwell_ms()
        switches = self.rapid_switches

        if switches >= 5 and avg_dwell < 3000.0:
            return "RESTLESS"
        if self.tab_flickers >= 3:
            return "TAB_HUNTING"
        if switches >= 3:
            return "SWITCHING"
        return "NORMAL"

    def reset(self) -> None:
        """Clear all micro counters for the next aggregation cycle."""
        self.rapid_switches = 0
        self.unique_apps = set()
        self.tab_flickers = 0
        self.total_dwell_ms = 0
        self.events = []

    def to_dict(self) -> Dict[str, Any]:
        """Convert micro-behavior metrics to a JSON-serializable dictionary.

        Returns:
            Dictionary containing serialized metrics and behavioral pattern.
        """
        return {
            "rapid_switches": self.rapid_switches,
            "unique_apps": sorted(list(self.unique_apps)),
            "tab_flickers": self.tab_flickers,
            "total_dwell_ms": self.total_dwell_ms,
            "avg_dwell_ms": round(self.avg_dwell_ms(), 2),
            "pattern": self.pattern(),
            "events_count": len(self.events),
            "events": copy.deepcopy(self.events),
        }


class Splitter:
    """Routes incoming collector events to MAIN or MICRO processing streams."""

    def __init__(self, chunker: Optional[Any] = None) -> None:
        """Initialize the Splitter with micro counters and downstream chunker.

        Args:
            chunker: Downstream chunker instance providing an add_event(event, micro) method.
        """
        self.chunker = chunker
        self.micro = MicroCounters()

    def set_chunker(self, chunker: Any) -> None:
        """Attach or update the downstream Chunker instance."""
        self.chunker = chunker

    def route(self, event: Dict[str, Any]) -> None:
        """Route event based on dwell time threshold.

        - dwell >= 10,000ms: dispatches to chunker.add_event(event, micro),
          carrying a snapshot of accumulated micro behavior, then resets micro counters.
        - dwell < 10,000ms: appends to micro counters to track restless patterns.

        Args:
            event: Window event dictionary containing dwell_ms.
        """
        dwell = int(event.get("dwell_ms", 0))

        if dwell >= MICRO_THRESHOLD_MS:
            # Main focus stream event: capture snapshot of micro context
            micro_snapshot = self.micro.to_dict()

            if self.chunker is not None and hasattr(self.chunker, "add_event"):
                self.chunker.add_event(event, micro_snapshot)

            # Reset micro state after handing off to chunker
            self.micro.reset()
        else:
            # Micro stream event: sub-10s flicker/distraction indicator
            self.micro.add(event)
