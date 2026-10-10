import re
from urllib.parse import unquote

# ── Anchor apps (real work happening) ──────────────────────────
ANCHOR_APPS = {
    "Code", "VS Code", "Visual Studio Code", "idea64", "IntelliJ", "Figma", "EXCEL", "Excel", "WINWORD", "Word",
    "devenv", "pycharm64", "PyCharm", "webstorm64", "rider64"
}

# ── YouTube title keyword classifier ───────────────────────────
YOUTUBE_LEARNING = {
    "tutorial", "how to", "explained", "course", "lecture",
    "lesson", "learn", "guide", "introduction to", "crash course",
    "workshop", "masterclass", "deep dive", "walkthrough",
    "switch case", "algorithm", "data structure", "programming",
    "python", "javascript", "react", "sql", "css", "html",
    "machine learning", "neural", "debugging", "code review",
    "system design", "interview", "leetcode", "project build"
}

YOUTUBE_WELLNESS = {
    "anxiety", "stress", "depression", "loneliness", "mental health",
    "therapy", "meditation", "mindfulness", "sleep", "burnout",
    "trauma", "healing", "self care", "emotional"
}

YOUTUBE_MOTIVATION = {
    "dream", "motivation", "procrastination", "discipline",
    "productivity", "neuroscience", "habit", "focus",
    "do nothing", "lazy", "goals", "success", "mindset",
    "self improvement", "growth"
}

YOUTUBE_ENTERTAINMENT = {
    "vlog", "funny", "meme", "comedy", "reaction",
    "shorts", "gaming", "music video", "trailer",
    "highlights", "fails", "prank", "challenge"
}

# ── Google Search query classifier ─────────────────────────────
SEARCH_LEARNING = {
    "how to", "what is", "why does", "difference between",
    "error", "fix", "debug", "not working", "example",
    "documentation", "vs ", "tutorial", "undefined", "syntax"
}

SEARCH_UTILITY = {
    "web player", "online", "login", "download", "install",
    "converter", "generator", "free", "app"
}

# ── VS Code file type classifier ────────────────────────────────
VSCODE_DEEP_WORK = {".py", ".js", ".ts", ".jsx", ".tsx", ".java",
                     ".cpp", ".c", ".go", ".rs", ".php", ".rb",
                     ".html", ".css", ".scss", ".vue", ".svelte"}

VSCODE_ADMIN = {"release notes", "welcome", "walkthrough",
                 "get started", "settings", "keybindings",
                 "extensions", "output", "terminal"}

VSCODE_CONFIG = {".json", ".yaml", ".yml", ".toml", ".env",
                  ".gitignore", ".lock", "package.json",
                  "requirements.txt", "dockerfile"}

VSCODE_DOCS = {".md", ".txt", ".rst", "readme"}


def classify_youtube(title: str) -> dict:
    """
    Extracts video title from window title and classifies it.
    Input: "Switch Case - YouTube" or "(4) Some Video - YouTube"
    """
    # Strip notification count and "- YouTube" suffix
    clean = re.sub(r'^\(\d+\)\s*', '', title)
    video_title = re.sub(r'\s*-\s*YouTube\s*$', '', clean,
                          flags=re.IGNORECASE).lower()

    for kw in YOUTUBE_LEARNING:
        if kw in video_title:
            return {"category": "Learning",
                    "sub": "tutorial",
                    "video_title": video_title}

    for kw in YOUTUBE_WELLNESS:
        if kw in video_title:
            return {"category": "Wellness",
                    "sub": "mental_health",
                    "video_title": video_title}

    for kw in YOUTUBE_MOTIVATION:
        if kw in video_title:
            return {"category": "Distraction",
                    "sub": "motivational_rabbit_hole",
                    "video_title": video_title}

    for kw in YOUTUBE_ENTERTAINMENT:
        if kw in video_title:
            return {"category": "Entertainment",
                    "sub": "passive_entertainment",
                    "video_title": video_title}

    # No keyword match — unknown YouTube content
    return {"category": "Entertainment",
            "sub": "unclassified_video",
            "video_title": video_title}


def classify_vscode(title: str) -> dict:
    """
    Extracts project name and file type from VS Code window title.
    Input: "index.html - MyProject - Visual Studio Code"
    """
    # Check for admin/setup screens first
    title_lower = title.lower()
    for admin_kw in VSCODE_ADMIN:
        if admin_kw in title_lower:
            return {"category": "Admin",
                    "sub": "vscode_setup",
                    "project": None,
                    "file": None}

    # Pattern: "filename - ProjectName - Visual Studio Code" or "filename - ProjectName"
    match = re.match(
        r'^(.+?)\s*-\s*([^-\n]+?)(?:\s*-\s*Visual Studio Code)?$', title)
    if match:
        filename = match.group(1).strip()
        project = unquote(match.group(2).strip())

        # Get file extension
        ext_match = re.search(r'(\.[a-zA-Z0-9]+)$', filename)
        ext = ext_match.group(1).lower() if ext_match else ""

        if ext in VSCODE_DEEP_WORK:
            return {"category": "Deep Work",
                    "sub": f"coding_{ext.strip('.')}",
                    "project": project,
                    "file": filename}

        if ext in VSCODE_CONFIG:
            return {"category": "Admin",
                    "sub": "config_file",
                    "project": project,
                    "file": filename}

        if ext in VSCODE_DOCS:
            return {"category": "Learning",
                    "sub": "documentation",
                    "project": project,
                    "file": filename}

    if "ts assignment" in title_lower or "assignment" in title_lower:
        return {"category": "Deep Work",
                "sub": "student_assignment",
                "project": "TS Assignment",
                "file": "TS Assignment"}

    # VS Code open but no file — navigation/setup
    return {"category": "Admin",
            "sub": "vscode_navigation",
            "project": None,
            "file": None}


def classify_chrome(title: str) -> dict:
    """
    Classifies Chrome tabs by extracting semantic signal from title.
    """
    # ── YouTube ──────────────────────────────────────────────
    if "youtube" in title.lower():
        # Check notification count → distraction signal
        notif_match = re.match(r'^\((\d+)\)', title)
        notif_count = int(notif_match.group(1)) if notif_match else 0

        if "youtube" == title.strip().lower() or \
           re.match(r'^\(\d+\)\s*youtube\s*$', title, re.IGNORECASE):
            # Homepage or bare notification tab
            return {"category": "Distraction",
                    "sub": "youtube_browsing",
                    "notif_count": notif_count}

        result = classify_youtube(title)
        result["notif_count"] = notif_count
        return result

    # ── Spotify ──────────────────────────────────────────────
    if "spotify" in title.lower():
        if "google search" in title.lower():
            return {"category": "Utility", "sub": "searching_for_spotify"}
        if " - album" in title.lower() or " - playlist" in title.lower() \
           or "web player" in title.lower():
            return {"category": "Ambient", "sub": "music_setup"}
        return {"category": "Ambient", "sub": "music_playing"}

    # ── Google Search ────────────────────────────────────────
    if "google search" in title.lower() or \
       title.lower().endswith("- google chrome") and \
       "- google search" in title.lower():
        # Extract query
        query = re.sub(r'\s*-\s*Google Search.*$', '', title,
                       flags=re.IGNORECASE).lower().strip()
        for kw in SEARCH_LEARNING:
            if kw in query:
                return {"category": "Learning",
                        "sub": "research_search",
                        "query": query}
        for kw in SEARCH_UTILITY:
            if kw in query:
                return {"category": "Utility",
                        "sub": "tool_search",
                        "query": query}
        return {"category": "Utility",
                "sub": "general_search",
                "query": query}

    # ── ChatGPT / Claude / AI tools ─────────────────────────
    if "chatgpt" in title.lower() or "claude" in title.lower():
        return {"category": "AI Tool", "sub": "ai_assistant"}

    # ── GitHub ───────────────────────────────────────────────
    if "github" in title.lower():
        if "pull request" in title.lower() or "pr" in title.lower():
            return {"category": "Deep Work", "sub": "code_review"}
        if "issue" in title.lower():
            return {"category": "Communication", "sub": "issue_tracking"}
        return {"category": "Deep Work", "sub": "github_browsing"}

    # ── Stack Overflow / Docs ────────────────────────────────
    if "stack overflow" in title.lower() or \
       "mdn web docs" in title.lower() or \
       "documentation" in title.lower():
        return {"category": "Learning", "sub": "technical_reference"}

    # ── New Tab ──────────────────────────────────────────────
    if title.strip().lower() in ("new tab", ""):
        return {"category": "Utility", "sub": "new_tab_navigation"}

    return {"category": "Utility", "sub": "general_browsing"}


def get_enriched_event(app: str, title: str) -> dict:
    """
    Main enrichment function. Returns full classification dict
    with category, sub-category, and extracted metadata.
    Call this instead of get_category().
    """
    app_clean = app.replace(".exe", "").strip()

    if app_clean in ("Code", "VS Code", "Visual Studio Code"):
        result = classify_vscode(title)
        result["app"] = "VS Code"
        return result

    if app_clean in ("chrome", "Google Chrome", "msedge", "firefox", "Chrome"):
        result = classify_chrome(title)
        result["app"] = app_clean
        return result

    if app_clean == "Slack":
        return {"category": "Communication",
                "sub": "messaging", "app": "Slack"}

    if app_clean in ("Zoom", "Teams", "meet"):
        return {"category": "Meeting",
                "sub": "video_call", "app": app_clean}

    if app_clean in ("PowerShell", "cmd", "Terminal", "WindowsTerminal"):
        return {"category": "Deep Work",
                "sub": "terminal", "app": app_clean}

    if app_clean in ("explorer", "File Explorer"):
        return {"category": "Utility",
                "sub": "file_navigation", "app": app_clean}

    if app_clean == "SearchHost":
        return {"category": "Utility",
                "sub": "windows_search", "app": app_clean}

    return {"category": "Utility", "sub": "other", "app": app_clean}


def is_anchor(app: str) -> bool:
    clean = app.replace(".exe", "").strip()
    return clean in ANCHOR_APPS or clean.lower() in {a.lower() for a in ANCHOR_APPS}


# Backward compatibility — splitter still calls get_category()
def get_category(app: str, title: str) -> str:
    return get_enriched_event(app, title)["category"]
