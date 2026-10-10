"""ChronoTrace Main Entry Point.

Wires together the full 5-layer pipeline:
1. WindowCollector (pywin32 / psutil window sampling)
2. Splitter (Separates >=10s MAIN vs <10s MICRO streams)
3. Chunker (Boundary detection: IDLE_GAP, ANCHOR_OPENED, CATEGORY_SHIFT, MAX_DURATION)
4. Aggregator (JSON payload builder with micro behavior & return-to-anchor detection)
5. LLMEngine (Gemini real-time intent classification & end-of-day multi-chunk synthesis)
6. IdleDetector (Monitors user inactivity gaps)
7. FastAPI Server (Uvicorn REST API backend)
"""

from datetime import datetime, timezone
import logging
import os
import signal
import sys
import threading
import time
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("chronotrace.main")

# Ensure root directory on Python path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from api.server import app
from collector.win_collector import WinCollector
from config import IDLE_GAP_S
from pipeline.aggregator import Aggregator
from pipeline.chunker import Chunker
from pipeline.idle_detector import IdleDetector
from pipeline.llm_engine import LLMEngine
from pipeline.splitter import Splitter
from storage.db import Database

# Optional scheduler import
try:
    import schedule
    SCHEDULE_AVAILABLE = True
except ImportError:
    schedule = None
    SCHEDULE_AVAILABLE = False


class ChronoTraceAgent:
    """Orchestrates ChronoTrace components and lifecycle management."""

    def __init__(self) -> None:
        logger.info("Initializing ChronoTrace Agent...")

        # 1. Database layer
        self.db = Database()

        # 2. LLM Engine (Gemini)
        self.llm_engine = LLMEngine(db=self.db)

        # 3. Aggregator layer
        self.aggregator = Aggregator(llm_engine=self.llm_engine)

        # 4. Chunker layer
        self.chunker = Chunker(on_chunk_complete=self._on_chunk_complete)

        # 5. Splitter layer
        self.splitter = Splitter(chunker=self.chunker)

        # 6. Idle Detector layer
        self.idle_detector = IdleDetector(chunker=self.chunker, idle_gap_s=float(IDLE_GAP_S))

        # 7. Window Collector layer
        # Hook splitter routing to also update idle detector
        original_route = self.splitter.route

        def instrumented_route(event):
            self.idle_detector.mark_event()
            return original_route(event)

        self.splitter.route = instrumented_route
        self.collector = WinCollector(splitter=self.splitter, poll_interval_s=0.5)

        self._running = False
        self._scheduler_thread: Optional[threading.Thread] = None
        self._api_thread: Optional[threading.Thread] = None

    def _on_chunk_complete(self, chunk) -> None:
        """Callback invoked when a chunk is finalized by the Chunker."""
        summary = self.aggregator.process(chunk)
        logger.info(
            f"Chunk completed: ID={summary.get('chunk_id')} | Duration={summary.get('duration_s')}s | "
            f"Anchor={summary.get('anchor_app')} | Returned={summary.get('returned_to_anchor')} | "
            f"Micro={summary.get('micro_behavior', {}).get('dominant_pattern')}"
        )

    def run_daily_synthesis(self) -> None:
        """Execute end-of-day multi-chunk analysis pass."""
        today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        logger.info(f"Running scheduled end-of-day synthesis for {today_str}...")
        try:
            result = self.llm_engine.end_of_day_pass(today_str)
            logger.info(f"End-of-day synthesis completed: {result.get('daily_narrative')}")
        except Exception as e:
            logger.error(f"Error in end-of-day synthesis: {e}", exc_info=True)

    def _start_scheduler(self) -> None:
        """Background thread executing scheduled end-of-day jobs."""
        if not SCHEDULE_AVAILABLE:
            logger.warning("Schedule library not installed. Daily synthesis at 21:00 requires manual invocation.")
            return

        schedule.every().day.at("21:00").do(self.run_daily_synthesis)

        def scheduler_worker():
            while self._running:
                schedule.run_pending()
                time.sleep(30)

        self._scheduler_thread = threading.Thread(
            target=scheduler_worker,
            name="ChronoTraceScheduler",
            daemon=True,
        )
        self._scheduler_thread.start()
        logger.info("Scheduled end-of-day synthesis daily at 21:00.")

    def _start_api_server(self, port: int = 8000) -> None:
        """Launch the FastAPI server using Uvicorn in a background daemon thread."""
        def uvicorn_worker():
            try:
                import uvicorn
                uvicorn.run(app, host="0.0.0.0", port=port, log_level="warning")
            except ImportError:
                logger.warning("Uvicorn is not installed; FastAPI background server could not be started.")
            except Exception as e:
                logger.error(f"Error in FastAPI server thread: {e}", exc_info=True)

        self._api_thread = threading.Thread(
            target=uvicorn_worker,
            name="ChronoTraceAPIServer",
            daemon=True,
        )
        self._api_thread.start()
        logger.info(f"FastAPI Server running in daemon thread at http://127.0.0.1:{port}")

    def start(self) -> None:
        """Boot up all pipelines and run the collector on the main thread."""
        self._running = True

        # Print banner
        print("\n" + "=" * 65)
        print("  ChronoTrace - Passive Activity Reconstruction Agent")
        print("=" * 65)
        print("  API Server:        http://127.0.0.1:8000")
        print("  API Docs:          http://127.0.0.1:8000/docs")
        print("  Database:          chronotrace.db")
        print("  Collector Cadence: 500ms")
        print("  End-of-Day Pass:   Daily at 21:00")
        print("=" * 65 + "\n")

        # 1. Start FastAPI server
        self._start_api_server(port=8000)

        # 2. Start Idle Detector
        self.idle_detector.start()

        # 3. Start Daily Scheduler
        self._start_scheduler()

        # 4. Run Collector on main thread (blocking until interrupt)
        try:
            self.collector.start()
            logger.info("ChronoTrace collector actively monitoring window transitions. Press Ctrl+C to halt.")
            while self._running:
                time.sleep(0.5)
        except (KeyboardInterrupt, SystemExit):
            logger.info("Received shutdown signal. Stopping ChronoTrace gracefully...")
        finally:
            self.stop()

    def stop(self) -> None:
        """Gracefully halt all background workers and flush open chunks."""
        self._running = False
        logger.info("Halting Collector...")
        self.collector.stop()
        logger.info("Halting Idle Detector...")
        self.idle_detector.stop()
        # Force finalize any open work chunk before exiting
        final_chunk = self.chunker.force_close(reason="SHUTDOWN")
        if final_chunk and final_chunk.events:
            logger.info(f"Persisted final session chunk prior to shutdown.")
        logger.info("ChronoTrace stopped successfully.")


def main() -> None:
    """Program entry point."""
    agent = ChronoTraceAgent()

    # Graceful signal handler
    def handle_sigterm(sig, frame):
        logger.info("SIGTERM received.")
        agent.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_sigterm)
    signal.signal(signal.SIGTERM, handle_sigterm)

    agent.start()


if __name__ == "__main__":
    main()
