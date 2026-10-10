"""ChronoTrace Database Storage Layer.

Handles SQLite connection management, schema migrations, and CRUD operations for
raw window events, structured session chunks, and daily summarized analytics.
"""

from datetime import datetime, timedelta, timezone
import json
import logging
from pathlib import Path
import sqlite3
import threading
from typing import Any, Dict, List, Optional
import sys

# Ensure root directory is on Python path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import DB_PATH

logger = logging.getLogger("chronotrace.db")


class Database:
    """Thread-safe SQLite database manager for ChronoTrace."""

    def __init__(self, db_path: Optional[Path] = None) -> None:
        """Initialize database connection pool and bootstrap schema.

        Args:
            db_path: Path to SQLite database file. Defaults to config.DB_PATH.
        """
        self.db_path = Path(db_path or DB_PATH)
        self._local = threading.local()
        self.init_db()

    def get_connection(self) -> sqlite3.Connection:
        """Return a thread-local SQLite database connection."""
        if not hasattr(self._local, "conn") or self._local.conn is None:
            conn = sqlite3.connect(
                str(self.db_path),
                timeout=20.0,
                check_same_thread=False,
            )
            conn.row_factory = sqlite3.Row
            # Enable WAL mode for concurrent reads and writes
            try:
                conn.execute("PRAGMA journal_mode=WAL;")
                conn.execute("PRAGMA synchronous=NORMAL;")
            except Exception:
                pass
            self._local.conn = conn
        return self._local.conn

    def init_db(self) -> None:
        """Execute schema.sql script to ensure tables and indexes exist."""
        schema_file = Path(__file__).resolve().parent / "schema.sql"
        if not schema_file.exists():
            logger.warning(f"Schema file not found at {schema_file}")
            return

        with open(schema_file, "r", encoding="utf-8") as f:
            schema_sql = f.read()

        conn = self.get_connection()
        with conn:
            conn.executescript(schema_sql)
        logger.info(f"Initialized ChronoTrace database at {self.db_path}")

    # ==========================================
    # RAW EVENTS
    # ==========================================

    def save_raw_event(self, event: Dict[str, Any]) -> int:
        """Persist a single raw window event.

        Args:
            event: Event dict with timestamp, app_name, window_title, category, dwell_ms, keyboard_events.

        Returns:
            Inserted row ID.
        """
        conn = self.get_connection()
        query = """
            INSERT INTO raw_events (timestamp, app_name, window_title, category, dwell_ms, keyboard_events)
            VALUES (?, ?, ?, ?, ?, ?)
        """
        with conn:
            cur = conn.execute(
                query,
                (
                    event.get("timestamp", datetime.now(timezone.utc).isoformat()),
                    event.get("app_name", "Unknown"),
                    event.get("window_title", ""),
                    event.get("category", "Utility"),
                    int(event.get("dwell_ms", 0)),
                    int(event.get("keyboard_events", 0)),
                ),
            )
            return cur.lastrowid

    def prune_raw_events(self, older_than_hours: int = 48) -> int:
        """Remove raw events older than the specified retention window.

        Args:
            older_than_hours: Hours of raw event history to retain (default: 48).

        Returns:
            Count of rows deleted.
        """
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=older_than_hours)).isoformat()
        conn = self.get_connection()
        query = "DELETE FROM raw_events WHERE timestamp < ?"
        with conn:
            cur = conn.execute(query, (cutoff,))
            deleted = cur.rowcount
        logger.info(f"Pruned {deleted} raw events older than {older_than_hours} hours.")
        return deleted

    # ==========================================
    # SESSIONS (CHUNKS)
    # ==========================================

    def save_session(self, session_dict: Dict[str, Any]) -> None:
        """Persist or update an aggregated, classified work session chunk.

        Args:
            session_dict: Complete session payload containing summary and LLM classification.
        """
        conn = self.get_connection()

        chunk_id = session_dict.get("chunk_id", "")
        # Extract date string (YYYY-MM-DD) from chunk_id or current time
        date_str = ""
        if chunk_id and "_" in chunk_id:
            raw_date = chunk_id.split("_")[0]
            if len(raw_date) == 8:
                date_str = f"{raw_date[:4]}-{raw_date[4:6]}-{raw_date[6:8]}"
        if not date_str:
            date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        start_ts = session_dict.get("start_time", "")
        end_ts = session_dict.get("end_time", "")
        duration_s = float(session_dict.get("duration_s", 0.0))
        intent = session_dict.get("intent", "DEEP_WORK")
        confidence = float(session_dict.get("confidence", 1.0))
        primary_task = session_dict.get("primary_task", "")
        distraction_detected = 1 if session_dict.get("distraction_detected") else 0
        distraction_type = session_dict.get("distraction_type")
        work_state = session_dict.get("work_state", "settled")
        summary_text = session_dict.get("summary", "")

        unresolved = session_dict.get("unresolved_threads", [])
        unresolved_json = json.dumps(unresolved) if isinstance(unresolved, list) else str(unresolved)

        anchor_app = session_dict.get("anchor_app")
        returned_to_anchor = 1 if session_dict.get("returned_to_anchor") else 0

        keyboard_rate = float(session_dict.get("keyboard", {}).get("rate_per_min", 0.0))
        micro_behavior = session_dict.get("micro_behavior", {})
        micro_pattern = micro_behavior.get("dominant_pattern", "NORMAL")
        rapid_switches = int(micro_behavior.get("total_rapid_switches", 0))
        session_start_restless = 1 if session_dict.get("session_start_restless") else 0

        # Preserve raw payload for full context
        raw_summary_json = json.dumps(session_dict)
        llm_output_json = json.dumps({
            "intent": intent,
            "confidence": confidence,
            "primary_task": primary_task,
            "distraction_detected": bool(distraction_detected),
            "distraction_type": distraction_type,
            "work_state": work_state,
            "summary": summary_text,
            "unresolved_threads": unresolved,
        })

        query = """
            INSERT INTO sessions (
                chunk_id, date, start_ts, end_ts, duration_s, intent, confidence,
                primary_task, distraction_detected, distraction_type, work_state,
                summary, unresolved_threads, anchor_app, returned_to_anchor,
                keyboard_rate, micro_pattern, session_start_restless, rapid_switches,
                raw_summary, llm_output, user_corrected
            ) VALUES (
                ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?,
                ?, ?, ?, ?,
                ?, ?, ?, ?,
                ?, ?, 0
            )
            ON CONFLICT(chunk_id) DO UPDATE SET
                date=excluded.date,
                start_ts=excluded.start_ts,
                end_ts=excluded.end_ts,
                duration_s=excluded.duration_s,
                intent=excluded.intent,
                confidence=excluded.confidence,
                primary_task=excluded.primary_task,
                distraction_detected=excluded.distraction_detected,
                distraction_type=excluded.distraction_type,
                work_state=excluded.work_state,
                summary=excluded.summary,
                unresolved_threads=excluded.unresolved_threads,
                anchor_app=excluded.anchor_app,
                returned_to_anchor=excluded.returned_to_anchor,
                keyboard_rate=excluded.keyboard_rate,
                micro_pattern=excluded.micro_pattern,
                session_start_restless=excluded.session_start_restless,
                rapid_switches=excluded.rapid_switches,
                raw_summary=excluded.raw_summary,
                llm_output=excluded.llm_output
        """

        with conn:
            conn.execute(
                query,
                (
                    chunk_id, date_str, start_ts, end_ts, duration_s, intent, confidence,
                    primary_task, distraction_detected, distraction_type, work_state,
                    summary_text, unresolved_json, anchor_app, returned_to_anchor,
                    keyboard_rate, micro_pattern, session_start_restless, rapid_switches,
                    raw_summary_json, llm_output_json,
                ),
            )

    def _row_to_session_dict(self, row: sqlite3.Row) -> Dict[str, Any]:
        """Deserialize database row into dictionary format."""
        d = dict(row)
        d["distraction_detected"] = bool(d.get("distraction_detected", 0))
        d["returned_to_anchor"] = bool(d.get("returned_to_anchor", 0))
        d["session_start_restless"] = bool(d.get("session_start_restless", 0))
        d["user_corrected"] = bool(d.get("user_corrected", 0))

        # Safely parse JSON columns
        try:
            d["unresolved_threads"] = json.loads(d.get("unresolved_threads") or "[]")
        except Exception:
            d["unresolved_threads"] = []

        try:
            d["raw_summary"] = json.loads(d.get("raw_summary") or "{}")
        except Exception:
            d["raw_summary"] = {}

        try:
            d["llm_output"] = json.loads(d.get("llm_output") or "{}")
        except Exception:
            d["llm_output"] = {}

        return d

    def get_sessions_for_date(self, date: str) -> List[Dict[str, Any]]:
        """Retrieve all work sessions recorded on a specific date (YYYY-MM-DD or YYYYMMDD)."""
        formatted_date = date
        if len(date) == 8 and "-" not in date:
            formatted_date = f"{date[:4]}-{date[4:6]}-{date[6:8]}"

        conn = self.get_connection()
        query = "SELECT * FROM sessions WHERE date = ? ORDER BY start_ts ASC"
        cur = conn.execute(query, (formatted_date,))
        rows = cur.fetchall()
        return [self._row_to_session_dict(r) for r in rows]

    # Alias for interoperability
    def get_sessions_by_date(self, date: str) -> List[Dict[str, Any]]:
        return self.get_sessions_for_date(date)

    def get_chunks_for_date(self, date: str) -> List[Dict[str, Any]]:
        """Alias to return chunks/sessions for a specific date."""
        return self.get_sessions_for_date(date)

    def update_intent(self, chunk_id: str, intent: str, user_corrected: bool = True) -> bool:
        """Manually override the classified intent label for a session chunk.

        Args:
            chunk_id: Identifier of target session chunk.
            intent: New intent label.
            user_corrected: Flag indicating user manual override (default: True).

        Returns:
            True if row was successfully updated.
        """
        conn = self.get_connection()
        query = "UPDATE sessions SET intent = ?, user_corrected = ? WHERE chunk_id = ?"
        with conn:
            cur = conn.execute(query, (intent, 1 if user_corrected else 0, chunk_id))
            return cur.rowcount > 0

    # ==========================================
    # DAILY SUMMARIES
    # ==========================================

    def save_day_summary(self, date: str, summary_dict: Dict[str, Any]) -> None:
        """Persist day-level synthesized analysis.

        Args:
            date: Target date string (YYYY-MM-DD).
            summary_dict: Daily summary dictionary.
        """
        conn = self.get_connection()
        formatted_date = date
        if len(date) == 8 and "-" not in date:
            formatted_date = f"{date[:4]}-{date[4:6]}-{date[6:8]}"

        day_json_str = json.dumps(summary_dict)
        query = """
            INSERT INTO daily_summaries (
                date, total_deep_work_s, total_distraction_s, fragmentation_score,
                peak_focus_window, context_switches, daily_narrative, day_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(date) DO UPDATE SET
                total_deep_work_s=excluded.total_deep_work_s,
                total_distraction_s=excluded.total_distraction_s,
                fragmentation_score=excluded.fragmentation_score,
                peak_focus_window=excluded.peak_focus_window,
                context_switches=excluded.context_switches,
                daily_narrative=excluded.daily_narrative,
                day_json=excluded.day_json
        """

        with conn:
            conn.execute(
                query,
                (
                    formatted_date,
                    int(summary_dict.get("total_deep_work_s", 0)),
                    int(summary_dict.get("total_distraction_s", 0)),
                    float(summary_dict.get("fragmentation_score", 0.0)),
                    summary_dict.get("peak_focus_window", ""),
                    int(summary_dict.get("context_switches", 0)),
                    summary_dict.get("daily_narrative", ""),
                    day_json_str,
                ),
            )

    # Alias for interoperability
    def save_daily_summary(self, summary_dict: Dict[str, Any]) -> None:
        date = summary_dict.get("date") or datetime.now(timezone.utc).strftime("%Y-%m-%d")
        self.save_day_summary(date, summary_dict)

    def get_daily_summary(self, date: str) -> Optional[Dict[str, Any]]:
        """Retrieve stored day-level synthesis for a specified date."""
        formatted_date = date
        if len(date) == 8 and "-" not in date:
            formatted_date = f"{date[:4]}-{date[4:6]}-{date[6:8]}"

        conn = self.get_connection()
        query = "SELECT * FROM daily_summaries WHERE date = ?"
        cur = conn.execute(query, (formatted_date,))
        row = cur.fetchone()
        if not row:
            return None

        d = dict(row)
        try:
            d["day_json"] = json.loads(d.get("day_json") or "{}")
        except Exception:
            d["day_json"] = {}
        return d

    # ==========================================
    # RE-ENTRY AND SEARCH CAPABILITIES
    # ==========================================

    def get_last_active_project(self) -> Optional[Dict[str, Any]]:
        """Identify the most recent project or anchor application active in the system."""
        conn = self.get_connection()
        query = """
            SELECT * FROM sessions
            WHERE anchor_app IS NOT NULL AND anchor_app != ''
            ORDER BY date DESC, start_ts DESC
            LIMIT 1
        """
        cur = conn.execute(query)
        row = cur.fetchone()
        if row:
            return self._row_to_session_dict(row)
        return None

    def get_last_session_for_project(self, project: str) -> Optional[Dict[str, Any]]:
        """Find the latest work session matching a specific project or application keyword.

        Args:
            project: Project keyword or app name (e.g. "ChronoTrace", "Figma", "Marketing").

        Returns:
            Most recent session dictionary matching the criteria.
        """
        conn = self.get_connection()
        term = f"%{project.lower()}%"
        query = """
            SELECT * FROM sessions
            WHERE LOWER(anchor_app) LIKE ?
               OR LOWER(primary_task) LIKE ?
               OR LOWER(summary) LIKE ?
               OR LOWER(raw_summary) LIKE ?
            ORDER BY date DESC, start_ts DESC
            LIMIT 1
        """
        cur = conn.execute(query, (term, term, term, term))
        row = cur.fetchone()
        if row:
            return self._row_to_session_dict(row)
        return None

    def search_sessions(self, query: str) -> List[Dict[str, Any]]:
        """Full-text substring search across recorded sessions.

        Searches within summary, primary_task, anchor_app, and unresolved_threads.
        """
        conn = self.get_connection()
        term = f"%{query.lower()}%"
        sql = """
            SELECT * FROM sessions
            WHERE LOWER(summary) LIKE ?
               OR LOWER(primary_task) LIKE ?
               OR LOWER(anchor_app) LIKE ?
               OR LOWER(unresolved_threads) LIKE ?
            ORDER BY date DESC, start_ts DESC
            LIMIT 50
        """
        cur = conn.execute(sql, (term, term, term, term))
        rows = cur.fetchall()
        return [self._row_to_session_dict(r) for r in rows]

    def get_weekly_patterns(self) -> Dict[str, Any]:
        """Aggregate behavioral and focus metrics over the past 7 days."""
        conn = self.get_connection()
        start_date = (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%d")

        query = """
            SELECT date, intent, SUM(duration_s) as total_duration,
                   COUNT(*) as session_count,
                   SUM(rapid_switches) as total_switches
            FROM sessions
            WHERE date >= ?
            GROUP BY date, intent
            ORDER BY date ASC
        """
        cur = conn.execute(query, (start_date,))
        rows = cur.fetchall()

        daily_breakdown: Dict[str, Dict[str, float]] = {}
        for r in rows:
            d = r["date"]
            intent = r["intent"]
            dur = float(r["total_duration"] or 0)
            if d not in daily_breakdown:
                daily_breakdown[d] = {"DEEP_WORK": 0.0, "DISTRACTION": 0.0, "TOTAL": 0.0}
            if intent in ["DEEP_WORK", "LEARNING"]:
                daily_breakdown[d]["DEEP_WORK"] += dur
            elif intent in ["DISTRACTION", "DISTRACTION_BREAK"]:
                daily_breakdown[d]["DISTRACTION"] += dur
            daily_breakdown[d]["TOTAL"] += dur

        return {
            "start_date": start_date,
            "daily_breakdown": daily_breakdown,
        }

    def get_distraction_triggers(self) -> List[Dict[str, Any]]:
        """Identify primary triggers and applications precipitating distraction sessions."""
        conn = self.get_connection()
        query = """
            SELECT distraction_type, micro_pattern, COUNT(*) as occurrence_count,
                   AVG(duration_s) as avg_duration,
                   AVG(rapid_switches) as avg_switches
            FROM sessions
            WHERE distraction_detected = 1 OR intent IN ('DISTRACTION', 'DISTRACTION_BREAK')
            GROUP BY distraction_type, micro_pattern
            ORDER BY occurrence_count DESC
            LIMIT 10
        """
        cur = conn.execute(query)
        rows = cur.fetchall()
        return [dict(r) for r in rows]
