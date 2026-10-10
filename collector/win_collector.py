"""ChronoTrace Windows Event Collector.

Captures active foreground window transitions, process executables, dwell times,
and keyboard event frequencies every 500ms using the Windows pywin32 and psutil APIs.
Only emits an event when the foreground window or application changes.
"""

from datetime import datetime, timezone
import logging
import threading
import time
from typing import Any, Callable, Dict, Optional
import sys
from pathlib import Path

# Ensure root directory is on Python path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from collector.enricher import get_category

# Optional imports with graceful fallbacks for environments without pywin32
try:
    import win32gui
    import win32process
    import win32con
    import win32api
    import psutil
    PYWIN32_AVAILABLE = True
except ImportError:
    PYWIN32_AVAILABLE = False
    win32gui = None
    win32process = None
    win32con = None
    win32api = None
    psutil = None

logger = logging.getLogger("chronotrace.collector")


class KeyboardCounterHook:
    """Non-blocking low-level Windows keyboard hook thread.

    Counts keypress events without recording any keystroke content or identifiers
    to protect user privacy. Operates as a background daemon thread.
    """

    def __init__(self) -> None:
        self._count = 0
        self._lock = threading.Lock()
        self._hook_id = None
        self._thread: Optional[threading.Thread] = None
        self._running = False

    def increment(self) -> None:
        """Atomically increment the keypress counter."""
        with self._lock:
            self._count += 1

    def get_and_reset(self) -> int:
        """Retrieve total keystrokes recorded since last call and reset counter to zero."""
        with self._lock:
            current = self._count
            self._count = 0
            return current

    def start(self) -> None:
        """Launch the low-level hook daemon thread if running on Windows."""
        if not PYWIN32_AVAILABLE:
            logger.debug("pywin32 not available; running with synthetic keyboard hook counter.")
            return

        self._running = True
        self._thread = threading.Thread(target=self._run_hook_pump, name="ChronoTraceKeyHook", daemon=True)
        self._thread.start()

    def _run_hook_pump(self) -> None:
        """Internal worker function running Windows message pump for hook callbacks."""
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32

        WH_KEYBOARD_LL = 13
        WM_KEYDOWN = 0x0100
        WM_SYSKEYDOWN = 0x0104

        HOOKPROC = ctypes.WINFUNCTYPE(ctypes.c_ssize_t, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)

        def low_level_keyboard_proc(nCode, wParam, lParam):
            if nCode >= 0 and wParam in (WM_KEYDOWN, WM_SYSKEYDOWN):
                self.increment()
            return user32.CallNextHookEx(None, nCode, wParam, lParam)

        # Retain reference to callback to avoid garbage collection
        self._callback = HOOKPROC(low_level_keyboard_proc)
        h_mod = kernel32.GetModuleHandleW(None)
        self._hook_id = user32.SetWindowsHookExW(
            WH_KEYBOARD_LL,
            self._callback,
            h_mod,
            0
        )

        if not self._hook_id:
            logger.warning("Failed to install Windows WH_KEYBOARD_LL hook.")
            return

        msg = wintypes.MSG()
        while self._running:
            # Non-blocking message check to allow termination
            if user32.PeekMessageW(ctypes.byref(msg), 0, 0, 0, 1):
                user32.TranslateMessage(ctypes.byref(msg))
                user32.DispatchMessageW(ctypes.byref(msg))
            else:
                time.sleep(0.05)

        if self._hook_id:
            user32.UnhookWindowsHookEx(self._hook_id)
            self._hook_id = None

    def stop(self) -> None:
        """Stop the keyboard hook thread."""
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)


class WinCollector:
    """Monitors the active Windows foreground window and process name every 500ms.

    Calculates dwell times between switches, attaches key counts, and forwards
    formatted event dictionaries to the splitter.
    """

    def __init__(self, splitter: Any, poll_interval_s: float = 0.5) -> None:
        """Initialize the Windows event collector.

        Args:
            splitter: Pipeline Splitter instance possessing a route(event) method.
            poll_interval_s: Polling interval in seconds (default: 0.5s = 500ms).
        """
        self.splitter = splitter
        self.poll_interval_s = poll_interval_s
        self.keyboard_hook = KeyboardCounterHook()
        self._stop_event = threading.Event()
        self._worker_thread: Optional[threading.Thread] = None

        # Tracking state
        self._current_app: str = ""
        self._current_title: str = ""
        self._window_start_time: float = time.time()

    def get_active_window_info(self) -> tuple[str, str]:
        """Fetch current foreground window title and process executable name safely.

        Returns:
            Tuple of (app_name, window_title).
        """
        if not PYWIN32_AVAILABLE:
            return "SimulatedApp", "Simulated Window Title"

        try:
            hwnd = win32gui.GetForegroundWindow()
            if not hwnd:
                return "Desktop", "Windows Desktop"

            window_title = win32gui.GetWindowText(hwnd).strip()

            # Retrieve process ID and resolve executable name
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            app_name = "Unknown"

            if pid and psutil:
                try:
                    proc = psutil.Process(pid)
                    app_name = proc.name()
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess, Exception):
                    app_name = "Unknown"

            return app_name, window_title
        except Exception as e:
            logger.debug(f"Error querying active window: {e}")
            return "Unknown", "Unknown"

    def _emit_event(self, app_name: str, window_title: str, dwell_ms: int, key_count: int) -> None:
        """Package and route the completed window session event."""
        category = get_category(app_name, window_title)
        event: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "app_name": app_name,
            "window_title": window_title,
            "category": category,
            "dwell_ms": dwell_ms,
            "keyboard_events": key_count,
        }

        try:
            self.splitter.route(event)
        except Exception as e:
            logger.error(f"Error routing event through splitter: {e}", exc_info=True)

    def poll_once(self) -> None:
        """Perform a single 500ms polling cycle and emit event on window switch."""
        app, title = self.get_active_window_info()
        now = time.time()

        # Initial launch condition
        if not self._current_app and not self._current_title:
            self._current_app = app
            self._current_title = title
            self._window_start_time = now
            return

        # Check for window or application transition
        if app != self._current_app or title != self._current_title:
            dwell_ms = int((now - self._window_start_time) * 1000)
            key_count = self.keyboard_hook.get_and_reset()

            # Emit the finished window state
            self._emit_event(
                app_name=self._current_app,
                window_title=self._current_title,
                dwell_ms=dwell_ms,
                key_count=key_count,
            )

            # Update state for newly focused window
            self._current_app = app
            self._current_title = title
            self._window_start_time = now

    def _run_loop(self) -> None:
        """Continuous polling loop executed by the worker thread."""
        self.keyboard_hook.start()
        self._window_start_time = time.time()
        self._current_app, self._current_title = self.get_active_window_info()

        while not self._stop_event.is_set():
            self.poll_once()
            time.sleep(self.poll_interval_s)

        # Flush final open window state when collector halts
        now = time.time()
        if self._current_app or self._current_title:
            dwell_ms = int((now - self._window_start_time) * 1000)
            key_count = self.keyboard_hook.get_and_reset()
            self._emit_event(
                app_name=self._current_app,
                window_title=self._current_title,
                dwell_ms=dwell_ms,
                key_count=key_count,
            )

    def start(self) -> None:
        """Start the collector and keyboard hook in a background thread."""
        self._stop_event.clear()
        self._worker_thread = threading.Thread(
            target=self._run_loop,
            name="ChronoTraceCollector",
            daemon=True,
        )
        self._worker_thread.start()

    def stop(self) -> None:
        """Stop polling and teardown keyboard hooks."""
        self._stop_event.set()
        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=1.5)
        self.keyboard_hook.stop()
