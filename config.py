"""ChronoTrace Configuration Module.

Defines global thresholds, anchor application definitions, model identifiers,
and persistence settings for the ChronoTrace passive activity reconstruction agent.
"""

from pathlib import Path
from typing import Set

# Core timing thresholds
MICRO_THRESHOLD_MS: int = 10000  # Dwell < 10s belongs to MICRO stream
IDLE_GAP_S: int = 120            # Inactivity > 2 minutes splits chunks
MAX_CHUNK_DURATION_S: int = 1200 # 20 minutes maximum chunk size
CATEGORY_SHIFT_S: int = 30       # Sustained category shift threshold to trigger boundary

# Anchor applications (primary focus and IDE tools where intentional deep work occurs)
# Includes friendly display names and common Windows process executable basenames.
ANCHOR_APPS: Set[str] = {
    "VS Code",
    "Code",
    "Code.exe",
    "Figma",
    "Figma.exe",
    "Excel",
    "EXCEL.EXE",
    "Word",
    "WINWORD.EXE",
    "PyCharm",
    "pycharm64.exe",
    "IntelliJ",
    "idea64.exe",
    "devenv",
    "devenv.exe",
}

# Categorization taxonomies
CATEGORY_DEEP_WORK = "Deep Work"
CATEGORY_COMMUNICATION = "Communication"
CATEGORY_MEETING = "Meeting"
CATEGORY_LEARNING = "Learning"
CATEGORY_ENTERTAINMENT = "Entertainment"
CATEGORY_SOCIAL = "Social"
CATEGORY_AMBIENT = "Ambient"
CATEGORY_UTILITY = "Utility"
CATEGORY_AI_TOOL = "AI Tool"

VALID_CATEGORIES = {
    CATEGORY_DEEP_WORK,
    CATEGORY_COMMUNICATION,
    CATEGORY_MEETING,
    CATEGORY_LEARNING,
    CATEGORY_ENTERTAINMENT,
    CATEGORY_SOCIAL,
    CATEGORY_AMBIENT,
    CATEGORY_UTILITY,
    CATEGORY_AI_TOOL,
}

# LLM Intent Labels
INTENT_DEEP_WORK = "DEEP_WORK"
INTENT_LEARNING = "LEARNING"
INTENT_DISTRACTION = "DISTRACTION"
INTENT_DISTRACTION_BREAK = "DISTRACTION_BREAK"
INTENT_COMMUNICATION = "COMMUNICATION"
INTENT_AMBIENT = "AMBIENT"
INTENT_ADMIN = "ADMIN"
INTENT_RESTLESS_START = "RESTLESS_START"

VALID_INTENTS = {
    INTENT_DEEP_WORK,
    INTENT_LEARNING,
    INTENT_DISTRACTION,
    INTENT_DISTRACTION_BREAK,
    INTENT_COMMUNICATION,
    INTENT_AMBIENT,
    INTENT_ADMIN,
    INTENT_RESTLESS_START,
}

# Storage and LLM Model configuration
GEMINI_MODEL: str = "gemini-1.5-flash"
DB_PATH: Path = Path("chronotrace.db")

# Collector polling settings
COLLECTOR_POLL_INTERVAL_MS: int = 500  # 500ms sampling window
