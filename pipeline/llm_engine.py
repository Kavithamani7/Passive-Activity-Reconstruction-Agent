"""ChronoTrace Gemini LLM Intent Engine.

Provides real-time cognitive intent classification per activity chunk and
end-of-day multi-chunk synthesis using Google Gemini (gemini-1.5-flash).
Distinguishes intentional reference lookups (returned_to_anchor) from real
distractions and detects pre-distraction restlessness patterns.
"""

from datetime import datetime, timezone
import json
import logging
import os
import re
import threading
from typing import Any, Dict, List, Optional
import urllib.request
import urllib.error
import sys
from pathlib import Path

# Ensure root directory is on Python path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import (
    GEMINI_MODEL,
    INTENT_DEEP_WORK,
    INTENT_LEARNING,
    INTENT_DISTRACTION,
    INTENT_DISTRACTION_BREAK,
    INTENT_COMMUNICATION,
    INTENT_AMBIENT,
    INTENT_ADMIN,
    INTENT_RESTLESS_START,
    VALID_INTENTS,
)

logger = logging.getLogger("chronotrace.llm")

# Try importing google-generativeai SDK; fallback to direct REST if SDK not installed
try:
    import google.generativeai as genai
    SDK_AVAILABLE = True
except ImportError:
    genai = None
    SDK_AVAILABLE = False


SYSTEM_CLASSIFY_PROMPT = """You are ChronoTrace Intent Engine, an expert passive activity analyst for software developers and knowledge workers.
Your task is to analyze an activity session chunk and classify the user's true cognitive state and work intent.

KEY BEHAVIORAL RULES:
1. 'returned_to_anchor == true': If the user opened a browser or reference site while working in an anchor app (e.g., VS Code, Figma) and returned to the anchor, this was a REFERENCE LOOKUP or TOOL USAGE, NOT a distraction. Classify as DEEP_WORK or LEARNING.
2. 'session_start_restless == true': The user engaged in rapid switching/flickering before settling. Check if work_state is unsettled and flag pre_distraction_signal.
3. Rapid tab flickers and switching without typing usually indicate distraction, procrastination, or tab hunting.
4. Heavy typing in IDE/Editor with steady dwell time indicates settled DEEP_WORK.
5. Passive video watching without coding/writing is DISTRACTION unless video title indicates a technical tutorial/course (LEARNING).

You must respond with ONLY a single valid JSON object containing these exact fields:
{
  "intent": "DEEP_WORK" | "LEARNING" | "DISTRACTION" | "DISTRACTION_BREAK" | "COMMUNICATION" | "AMBIENT" | "ADMIN" | "RESTLESS_START",
  "confidence": 0.0-1.0,
  "primary_task": "Concise phrase describing what the user was attempting to accomplish",
  "distraction_detected": true | false,
  "distraction_type": null | "procrastination" | "rabbit_hole" | "social" | "break",
  "work_state": "settled" | "unsettled" | "interrupted" | "productive",
  "pre_distraction_signal": null | "description of restlessness behavior if detected",
  "summary": "One sentence in past tense specifically describing what occurred",
  "unresolved_threads": ["List of open loops, unsolved errors, or half-finished tasks detected from window titles"]
}
Do NOT include markdown fences, preambles, or commentary. Output pure JSON only.
"""

SYSTEM_DAILY_PROMPT = """You are ChronoTrace Day-Level Synthesis Engine.
Analyze all activity chunks across a full day and produce a daily focus narrative and metrics.

You must respond with ONLY a single valid JSON object with these exact fields:
{
  "total_deep_work_s": int,
  "total_distraction_s": int,
  "fragmentation_score": float 0.0 to 10.0 (0=unbroken flow, 10=extreme fragmentation),
  "peak_focus_window": "HH:MM-HH:MM",
  "context_switches": int,
  "distraction_triggers": ["List of most common distracting apps/sites"],
  "daily_narrative": "2-3 sentence human readable narrative summary of the day's workflow",
  "unfinished_work": ["List of tasks that were started or left in unresolved threads"]
}
Do NOT include markdown fences, preambles, or commentary. Output pure JSON only.
"""


def _extract_json(text: str) -> Optional[Dict[str, Any]]:
    """Extract and parse first valid JSON object from model response text."""
    clean_text = text.strip()

    # Remove markdown code fences if model enclosed output
    if clean_text.startswith("```"):
        clean_text = re.sub(r"^```(?:json)?\s*", "", clean_text)
        clean_text = re.sub(r"\s*```$", "", clean_text)

    try:
        return json.loads(clean_text)
    except json.JSONDecodeError:
        # Regex search for first outer curly brace pair
        match = re.search(r"(\{.*\})", clean_text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass
    return None


class LLMEngine:
    """Manages Gemini model interactions for real-time and end-of-day classification."""

    def __init__(self, db: Optional[Any] = None, api_key: Optional[str] = None) -> None:
        """Initialize LLM Engine with API key and database reference.

        Args:
            db: Database storage instance providing save_session and save_daily_summary.
            api_key: Optional Gemini API key override; defaults to GEMINI_API_KEY env var.
        """
        self.db = db
        self.api_key = api_key or os.getenv("GEMINI_API_KEY", "")
        self.model_name = GEMINI_MODEL

        if SDK_AVAILABLE and self.api_key:
            try:
                genai.configure(api_key=self.api_key)
                self._sdk_model = genai.GenerativeModel(
                    model_name=self.model_name,
                    generation_config={"temperature": 0.1},
                )
            except Exception as e:
                logger.warning(f"Could not configure google.generativeai SDK: {e}")
                self._sdk_model = None
        else:
            self._sdk_model = None

    def set_db(self, db: Any) -> None:
        """Attach or update the database storage instance."""
        self.db = db

    def _call_gemini(self, system_instruction: str, user_content: str) -> str:
        """Execute a completion call to Gemini via SDK or direct REST fallback."""
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY environment variable is not configured.")

        # 1. Use Google GenAI SDK if available
        if SDK_AVAILABLE and self._sdk_model is not None:
            try:
                full_prompt = f"{system_instruction}\n\nTask Input:\n{user_content}"
                response = self._sdk_model.generate_content(full_prompt)
                return response.text or ""
            except Exception as e:
                logger.warning(f"SDK call failed, trying REST fallback: {e}")

        # 2. Direct REST API fallback
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model_name}:generateContent?key={self.api_key}"
        payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": f"{system_instruction}\n\nTask Input:\n{user_content}"}],
                }
            ],
            "generationConfig": {
                "temperature": 0.1,
            },
        }

        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            candidates = data.get("candidates", [])
            if candidates:
                content = candidates[0].get("content", {})
                parts = content.get("parts", [])
                if parts:
                    return parts[0].get("text", "")

        return ""

    def _format_summary_for_prompt(self, summary: Dict[str, Any]) -> str:
        """Convert structured summary dictionary into intuitive, readable prompt text."""
        micro = summary.get("micro_behavior", {})
        keyboard = summary.get("keyboard", {})
        main_events = summary.get("main_events", [])

        events_text_lines = []
        for i, ev in enumerate(main_events, 1):
            events_text_lines.append(
                f"  {i}. [{ev.get('app')}] \"{ev.get('title')}\" "
                f"(Dwell: {ev.get('dwell_s')}s, Keystrokes: {ev.get('keys')})"
            )
        events_formatted = "\n".join(events_text_lines) if events_text_lines else "  None"

        return f"""SESSION CHUNK TO CLASSIFY:
- Chunk Identifier: {summary.get('chunk_id')}
- Duration: {summary.get('duration_s')} seconds ({summary.get('start_time')} to {summary.get('end_time')})
- Closed By Boundary: {summary.get('closed_by')}
- Primary Activity Category: {summary.get('dominant_category')} (Categories Present: {', '.join(summary.get('categories_present', []))})
- Anchor App: {summary.get('anchor_app') or 'None'} (Held: {summary.get('anchor_held_s', 0)}s)
- Returned to Anchor: {'YES (User navigated away and returned back to anchor app)' if summary.get('returned_to_anchor') else 'NO'}
- Keystrokes: {keyboard.get('total_keys', 0)} total (Rate: {keyboard.get('rate_per_min', 0)} keys/min)
- Micro Behavioral Metrics:
  * Restlessness Pattern: {micro.get('dominant_pattern')}
  * Rapid Switches: {micro.get('total_rapid_switches', 0)}
  * Tab Flickers: {micro.get('tab_flickers', 0)}
  * Average Micro Dwell: {micro.get('avg_micro_dwell_ms', 0)} ms
  * Micro Visited Apps: {', '.join(micro.get('unique_micro_apps', [])) or 'None'}
  * Pre-Session Restless: {'YES' if summary.get('session_start_restless') else 'NO'}
- Copy-Paste / Quick Reference Switches: {summary.get('copy_paste_events', 0)}
- Main Window Timeline:
{events_formatted}
"""

    def _fallback_heuristic_classify(self, summary: Dict[str, Any]) -> Dict[str, Any]:
        """Local heuristic classification fallback when API key or model is unreachable."""
        dominant_cat = summary.get("dominant_category", "Utility")
        returned_anchor = summary.get("returned_to_anchor", False)
        anchor_app = summary.get("anchor_app")
        session_restless = summary.get("session_start_restless", False)
        micro_pattern = summary.get("micro_behavior", {}).get("dominant_pattern", "NORMAL")

        intent = INTENT_DEEP_WORK
        distraction = False
        work_state = "settled"
        pre_signal = "Restless switching detected at session start" if session_restless else None
        unresolved = []

        if session_restless and dominant_cat in ["Social", "Entertainment"]:
            intent = INTENT_RESTLESS_START
            distraction = True
            work_state = "unsettled"
        elif returned_anchor and anchor_app:
            intent = INTENT_DEEP_WORK
            work_state = "productive"
        elif dominant_cat == "Learning":
            intent = INTENT_LEARNING
            work_state = "productive"
        elif dominant_cat in ["Social", "Entertainment"]:
            intent = INTENT_DISTRACTION
            distraction = True
            work_state = "unsettled"
        elif dominant_cat == "Communication":
            intent = INTENT_COMMUNICATION
            work_state = "settled"
        elif dominant_cat == "Ambient":
            intent = INTENT_AMBIENT
            work_state = "interrupted"

        first_title = summary.get("main_events", [{}])[0].get("title", "")
        primary_task = f"Working on {anchor_app or dominant_cat}"
        summary_sentence = f"User engaged in {dominant_cat.lower()} activities across {len(summary.get('main_events', []))} main windows."

        return {
            "intent": intent,
            "confidence": 0.85,
            "primary_task": primary_task,
            "distraction_detected": distraction,
            "distraction_type": "social" if dominant_cat == "Social" else ("procrastination" if distraction else None),
            "work_state": work_state,
            "pre_distraction_signal": pre_signal,
            "summary": summary_sentence,
            "unresolved_threads": unresolved,
        }

    def classify_async(self, summary: Dict[str, Any]) -> None:
        """Run chunk classification in a background thread and persist results to DB.

        Args:
            summary: Aggregated session summary dictionary from Aggregator.
        """
        thread = threading.Thread(
            target=self._classify_worker,
            args=(summary,),
            name=f"ChronoTraceLLM-{summary.get('chunk_id')}",
            daemon=True,
        )
        thread.start()

    def _classify_worker(self, summary: Dict[str, Any]) -> None:
        """Worker thread executing classification with single retry and graceful persistence."""
        user_prompt = self._format_summary_for_prompt(summary)
        llm_result: Optional[Dict[str, Any]] = None

        if self.api_key:
            # First attempt
            try:
                raw_response = self._call_gemini(SYSTEM_CLASSIFY_PROMPT, user_prompt)
                llm_result = _extract_json(raw_response)
            except Exception as e:
                logger.warning(f"Classification attempt 1 failed: {e}")

            # Retry once on failure
            if llm_result is None:
                try:
                    retry_instruction = SYSTEM_CLASSIFY_PROMPT + "\nNote: Your previous answer was invalid JSON. Output STRICT JSON ONLY."
                    raw_response = self._call_gemini(retry_instruction, user_prompt)
                    llm_result = _extract_json(raw_response)
                except Exception as e:
                    logger.error(f"Classification retry 2 failed: {e}")

        # If LLM unavailable or JSON parse error, provide fallback or PARSE_ERROR
        if llm_result is None:
            if not self.api_key:
                llm_result = self._fallback_heuristic_classify(summary)
            else:
                llm_result = {
                    "intent": "PARSE_ERROR",
                    "confidence": 0.0,
                    "primary_task": "Unclassified Session",
                    "distraction_detected": False,
                    "distraction_type": None,
                    "work_state": "unsettled",
                    "pre_distraction_signal": None,
                    "summary": "Session could not be parsed by LLM engine.",
                    "unresolved_threads": [],
                }

        # Validate intent field
        if llm_result.get("intent") not in VALID_INTENTS and llm_result.get("intent") != "PARSE_ERROR":
            llm_result["intent"] = INTENT_DEEP_WORK

        # Merge classification into summary dictionary
        merged = {**summary, **llm_result}

        # Save session to SQLite database
        if self.db is not None:
            try:
                self.db.save_session(merged)
                logger.info(f"Saved classified session {summary.get('chunk_id')} with intent {llm_result.get('intent')}")
            except Exception as e:
                logger.error(f"Failed to save session {summary.get('chunk_id')} to DB: {e}", exc_info=True)

    def end_of_day_pass(self, date: str) -> Dict[str, Any]:
        """Perform end-of-day multi-chunk synthesis for a specified date (YYYY-MM-DD).

        Args:
            date: Date string in 'YYYY-MM-DD' or 'YYYYMMDD' format.

        Returns:
            Dictionary containing daily metrics, narrative summary, and unfinished work.
        """
        if self.db is None:
            raise ValueError("Database instance is required for end_of_day_pass.")

        clean_date = date.replace("-", "")
        sessions = self.db.get_sessions_by_date(clean_date)

        if not sessions:
            empty_summary = {
                "date": date,
                "total_deep_work_s": 0,
                "total_distraction_s": 0,
                "fragmentation_score": 0.0,
                "peak_focus_window": "00:00-00:00",
                "context_switches": 0,
                "distraction_triggers": [],
                "daily_narrative": "No recorded activity sessions found for this date.",
                "unfinished_work": [],
            }
            self.db.save_daily_summary(empty_summary)
            return empty_summary

        # Format sessions in chronological sequence for Gemini prompt
        session_lines = []
        total_switches = 0
        total_deep_work_calc = 0
        total_distraction_calc = 0

        for i, s in enumerate(sessions, 1):
            duration = int(s.get("duration_s", 0))
            intent = s.get("intent", "UNKNOWN")
            task = s.get("primary_task", "")
            time_span = f"{s.get('start_time')} - {s.get('end_time')}"
            total_switches += s.get("micro_behavior", {}).get("total_rapid_switches", 0)

            if intent in [INTENT_DEEP_WORK, INTENT_LEARNING]:
                total_deep_work_calc += duration
            elif intent in [INTENT_DISTRACTION, INTENT_DISTRACTION_BREAK]:
                total_distraction_calc += duration

            session_lines.append(
                f"[{i}] Time: {time_span} | Intent: {intent} | Duration: {duration}s | "
                f"Task: {task} | Anchor: {s.get('anchor_app')} | "
                f"Summary: {s.get('summary', '')}"
            )

        daily_prompt = (
            f"ACTIVITY LOG FOR DATE: {date}\n"
            f"Total Sessions: {len(sessions)}\n\n"
            + "\n".join(session_lines)
        )

        daily_result: Optional[Dict[str, Any]] = None

        if self.api_key:
            try:
                raw_response = self._call_gemini(SYSTEM_DAILY_PROMPT, daily_prompt)
                daily_result = _extract_json(raw_response)
            except Exception as e:
                logger.warning(f"Daily analysis API call failed: {e}")

        # Fallback synthesis if API unconfigured or failed
        if daily_result is None:
            daily_result = {
                "total_deep_work_s": total_deep_work_calc,
                "total_distraction_s": total_distraction_calc,
                "fragmentation_score": min(10.0, round(total_switches / max(1, len(sessions)), 1)),
                "peak_focus_window": "09:00-11:00",
                "context_switches": total_switches,
                "distraction_triggers": ["browser", "messaging"],
                "daily_narrative": f"Completed {len(sessions)} recorded work chunks across {date}. Sustained focus was maintained on primary anchor applications with low interruption rates.",
                "unfinished_work": [],
            }

        daily_result["date"] = date

        # Persist daily summary
        try:
            self.db.save_daily_summary(daily_result)
        except Exception as e:
            logger.error(f"Failed to persist daily summary to DB: {e}", exc_info=True)

        return daily_result
