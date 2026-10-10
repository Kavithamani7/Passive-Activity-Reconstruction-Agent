-- ChronoTrace SQLite Database Schema
-- Provides tables for raw window transitions, classified work session chunks, and daily synthesized summaries.

CREATE TABLE IF NOT EXISTS raw_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    app_name TEXT NOT NULL,
    window_title TEXT,
    category TEXT,
    dwell_ms INTEGER NOT NULL,
    keyboard_events INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS sessions (
    chunk_id TEXT PRIMARY KEY,
    date TEXT NOT NULL,
    start_ts TEXT NOT NULL,
    end_ts TEXT NOT NULL,
    duration_s REAL NOT NULL,
    intent TEXT NOT NULL,
    confidence REAL DEFAULT 1.0,
    primary_task TEXT,
    distraction_detected INTEGER NOT NULL DEFAULT 0,
    distraction_type TEXT,
    work_state TEXT,
    summary TEXT,
    unresolved_threads TEXT,
    anchor_app TEXT,
    returned_to_anchor INTEGER NOT NULL DEFAULT 0,
    keyboard_rate REAL DEFAULT 0.0,
    micro_pattern TEXT DEFAULT 'NORMAL',
    session_start_restless INTEGER NOT NULL DEFAULT 0,
    rapid_switches INTEGER NOT NULL DEFAULT 0,
    raw_summary TEXT,
    llm_output TEXT,
    user_corrected INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS daily_summaries (
    date TEXT PRIMARY KEY,
    total_deep_work_s INTEGER NOT NULL DEFAULT 0,
    total_distraction_s INTEGER NOT NULL DEFAULT 0,
    fragmentation_score REAL NOT NULL DEFAULT 0.0,
    peak_focus_window TEXT,
    context_switches INTEGER NOT NULL DEFAULT 0,
    daily_narrative TEXT,
    day_json TEXT
);

CREATE INDEX IF NOT EXISTS idx_sessions_date ON sessions (date);
CREATE INDEX IF NOT EXISTS idx_sessions_intent ON sessions (intent);
CREATE INDEX IF NOT EXISTS idx_raw_events_timestamp ON raw_events (timestamp);
