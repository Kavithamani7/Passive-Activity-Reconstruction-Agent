"""ChronoTrace FastAPI Server.

Exposes REST API endpoints for the React dashboard and system integrations:
- Real-time work session streams
- Daily summaries and weekly fragmentation patterns
- Laptop wake re-entry briefings ("Last time on this project was X days ago...")
- Session search and user intent corrections
- Serves the standalone static HTML dashboard
"""

from datetime import datetime, timezone
import json
import logging
from typing import Any, Dict, List, Optional
import sys
from pathlib import Path

# Ensure root directory is on Python path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    from fastapi import FastAPI, HTTPException, Query
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.staticfiles import StaticFiles
    from fastapi.responses import FileResponse
    from pydantic import BaseModel, Field
    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False
    # Graceful stubs for environments prior to running pip install
    class BaseModel:
        def __init__(self, **kwargs):
            for k, v in kwargs.items():
                setattr(self, k, v)
    def Field(*args, **kwargs):
        return None
    class HTTPException(Exception):
        def __init__(self, status_code: int, detail: str):
            self.status_code = status_code
            self.detail = detail
    class FastAPI:
        def __init__(self, *args, **kwargs):
            pass
        def add_middleware(self, *args, **kwargs):
            pass
        def mount(self, *args, **kwargs):
            pass
        def get(self, *args, **kwargs):
            return lambda fn: fn
        def post(self, *args, **kwargs):
            return lambda fn: fn
    class Query:
        def __init__(self, *args, **kwargs):
            pass
    class StaticFiles:
        def __init__(self, *args, **kwargs):
            pass
    def FileResponse(path, *args, **kwargs):
        return path
    CORSMiddleware = None

from storage.db import Database

logger = logging.getLogger("chronotrace.api")

app = FastAPI(
    title="ChronoTrace API",
    description="Passive Activity Reconstruction & Cognitive Intent Classification Engine",
    version="1.0.0",
)

app.mount("/static", StaticFiles(directory="api"), name="static")

@app.get("/")
@app.get("/dashboard")
def serve_dashboard():
    return FileResponse("api/dashboard.html")

# CORS middleware for local React dev server and preview environments
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Shared Database instance
db = Database()


class IntentCorrectionRequest(BaseModel):
    intent: str = Field(..., description="Target intent label to apply to chunk")


@app.get("/health")
def health_check() -> Dict[str, str]:
    """Health status check."""
    return {"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat()}


@app.get("/api/current-window")
@app.get("/current-window")
def get_current_window() -> Dict[str, Any]:
    """Returns the single most recent raw event from the database."""
    conn = db.get_connection()
    cur = conn.execute("SELECT * FROM raw_events ORDER BY timestamp DESC LIMIT 1")
    row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="No raw events found in database.")
    return {
        "app_name": row["app_name"],
        "window_title": row["window_title"] or "",
        "category": row["category"] or "Utility",
        "timestamp": row["timestamp"],
        "dwell_ms": row["dwell_ms"],
    }


@app.get("/api/telemetry/raw")
@app.get("/telemetry/raw")
def get_telemetry_raw() -> List[Dict[str, Any]]:
    """Returns all raw_events for today ordered by timestamp ascending."""
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    conn = db.get_connection()
    cur = conn.execute(
        """
        SELECT * FROM raw_events
        WHERE timestamp LIKE ? OR date(timestamp) = date('now')
        ORDER BY timestamp ASC
        """,
        (f"{today_str}%",),
    )
    rows = cur.fetchall()
    if not rows:
        cur = conn.execute("SELECT * FROM raw_events ORDER BY timestamp ASC")
        rows = cur.fetchall()

    return [
        {
            "app_name": r["app_name"],
            "window_title": r["window_title"] or "",
            "category": r["category"] or "Utility",
            "timestamp": r["timestamp"],
            "dwell_ms": r["dwell_ms"],
        }
        for r in rows
    ]


@app.get("/sessions/today")
def get_sessions_today() -> List[Dict[str, Any]]:
    """Retrieve all recorded activity session chunks for the current day."""
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    sessions = db.get_sessions_for_date(today_str)
    if not sessions:
        sessions = db.get_all_sessions()
    return sessions


@app.get("/summary/today")
def get_summary_today() -> Dict[str, Any]:
    """Retrieve daily synthesized summary.

    Falls back to real-time aggregation across today's sessions if
    end-of-day synthesis has not yet occurred.
    """
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    stored = db.get_daily_summary(today_str)
    if stored:
        return stored

    # Real-time computed summary
    sessions = db.get_sessions_for_date(today_str)
    total_deep_work_s = sum(
        int(s.get("duration_s", 0))
        for s in sessions
        if s.get("intent") in ["DEEP_WORK", "LEARNING"]
    )
    total_distraction_s = sum(
        int(s.get("duration_s", 0))
        for s in sessions
        if s.get("intent") in ["DISTRACTION", "DISTRACTION_BREAK"]
    )
    total_switches = sum(int(s.get("rapid_switches", 0)) for s in sessions)
    frag_score = min(10.0, round(total_switches / max(1, len(sessions)), 1)) if sessions else 0.0

    return {
        "date": today_str,
        "total_deep_work_s": total_deep_work_s,
        "total_distraction_s": total_distraction_s,
        "fragmentation_score": frag_score,
        "peak_focus_window": "In Progress",
        "context_switches": total_switches,
        "daily_narrative": f"Recorded {len(sessions)} chunks today. Sustained deep work total: {total_deep_work_s // 60}m.",
        "unfinished_work": [
            thread
            for s in sessions
            for thread in s.get("unresolved_threads", [])
        ],
        "in_progress": True,
    }


@app.get("/patterns/week")
def get_patterns_week() -> Dict[str, Any]:
    """Retrieve aggregated focus and distraction patterns across the past 7 days."""
    return db.get_weekly_patterns()


@app.get("/reentry/{project}")
def get_reentry_briefing(project: str) -> Dict[str, Any]:
    """Generate a context reconstruction re-entry briefing on laptop wake.

    Informs user when they last worked on the specified project, what task was underway,
    and any open threads/unresolved loops left behind.
    """
    session: Optional[Dict[str, Any]] = None

    if project.lower() in ["latest", "current", "auto"]:
        session = db.get_last_active_project()
    else:
        session = db.get_last_session_for_project(project)

    if not session:
        return {
            "project": project,
            "found": False,
            "headline": f"No previous activity found for project '{project}'.",
            "unresolved_threads": [],
        }

    # Calculate elapsed duration
    date_str = session.get("date", "")
    time_str = session.get("start_ts", "00:00:00")
    now = datetime.now(timezone.utc)

    days_ago = 0
    time_desc = "recently"
    try:
        session_dt = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
        delta = now - session_dt
        days_ago = delta.days
        hours_ago = delta.seconds // 3600

        if days_ago == 0:
            time_desc = f"{hours_ago} hours ago" if hours_ago > 0 else "earlier today"
        elif days_ago == 1:
            time_desc = "yesterday"
        else:
            time_desc = f"{days_ago} days ago"
    except Exception:
        pass

    primary_task = session.get("primary_task") or "working on codebase"
    unresolved = session.get("unresolved_threads", [])
    anchor_app = session.get("anchor_app", project)

    unresolved_text = f"left {len(unresolved)} unresolved thread(s)" if unresolved else "left no open issues"
    headline = f"Last time on {anchor_app} was {time_desc}. You were {primary_task.lower()}, and {unresolved_text}."

    return {
        "project": anchor_app or project,
        "found": True,
        "days_ago": days_ago,
        "time_desc": time_desc,
        "headline": headline,
        "primary_task": primary_task,
        "summary": session.get("summary", ""),
        "unresolved_threads": unresolved,
        "last_session": session,
    }


@app.get("/search")
def search_sessions(q: str = Query(..., min_length=1, description="Search query string")) -> List[Dict[str, Any]]:
    """Search recorded activity sessions by keyword or app title."""
    return db.search_sessions(q)


@app.get("/distraction/patterns")
def get_distraction_patterns() -> List[Dict[str, Any]]:
    """Retrieve recurring distraction triggers, frequent sites, and restlessness patterns."""
    return db.get_distraction_triggers()


@app.post("/sessions/{chunk_id}/correct")
def correct_session_intent(chunk_id: str, payload: IntentCorrectionRequest) -> Dict[str, Any]:
    """Allow user to manually correct the intent label of a classified session."""
    success = db.update_intent(chunk_id=chunk_id, intent=payload.intent, user_corrected=True)
    if not success:
        raise HTTPException(status_code=404, detail=f"Session chunk '{chunk_id}' not found.")
    return {"status": "updated", "chunk_id": chunk_id, "intent": payload.intent}


def create_app() -> FastAPI:
    """Application factory for Uvicorn entry."""
    return app
