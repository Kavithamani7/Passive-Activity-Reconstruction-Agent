"""ChronoTrace Idle Detector.

Monitors user inactivity between foreground window transitions. If no events
occur for longer than IDLE_GAP_S (120s), closes the current open chunk to ensure
idle time is not erroneously counted towards active work dwell time.
"""

import logging
import threading
import time
from typing import Any, Optional
import sys
from pathlib import Path

# Ensure root directory is on Python path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import IDLE_GAP_S

logger = logging.getLogger("chronotrace.idle_detector")


class IdleDetector:
    """Watches elapsed time since the last recorded event and triggers chunk boundary closure."""

    def __init__(self, chunker: Any, idle_gap_s: float = float(IDLE_GAP_S)) -> None:
        """Initialize the idle detector.

        Args:
            chunker: Chunker instance providing force_close(reason).
            idle_gap_s: Threshold in seconds beyond which inactivity closes the active chunk.
        """
        self.chunker = chunker
        self.idle_gap_s = idle_gap_s
        self.last_event_time: float = time.time()
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def mark_event(self) -> None:
        """Update the timestamp of the most recent user activity event."""
        with self._lock:
            self.last_event_time = time.time()

    def _check_loop(self) -> None:
        """Periodic background worker checking for idle timeouts every 30 seconds."""
        logger.info(f"Idle detector started with {self.idle_gap_s}s threshold (30s check cadence).")
        while not self._stop_event.is_set():
            # Wait up to 30 seconds or until stopped
            if self._stop_event.wait(timeout=30.0):
                break

            with self._lock:
                elapsed = time.time() - self.last_event_time

            if elapsed >= self.idle_gap_s:
                if self.chunker is not None and hasattr(self.chunker, "force_close"):
                    closed = self.chunker.force_close(reason="IDLE_GAP")
                    if closed:
                        logger.info(f"Idle gap ({elapsed:.1f}s > {self.idle_gap_s}s) force-closed chunk {closed.start_ts}")

    def start(self) -> None:
        """Start the background idle detection daemon thread."""
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._check_loop,
            name="ChronoTraceIdleDetector",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        """Terminate the idle detector worker thread."""
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)
