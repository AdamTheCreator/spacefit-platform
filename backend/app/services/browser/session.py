"""
Session validation and management utilities.
"""

import json
from pathlib import Path
from datetime import datetime, timedelta

from app.core.config import settings


def get_session_age_hours(storage_path: Path) -> float | None:
    """Get the age of a session file in hours, or None if not found."""
    if not storage_path.exists():
        return None
    mtime = datetime.fromtimestamp(storage_path.stat().st_mtime)
    age = datetime.now() - mtime
    return age.total_seconds() / 3600


def is_session_valid(
    storage_path: Path,
    max_age_hours: int | None = None,
) -> bool:
    """
    Check if a stored session is still likely valid.

    Checks:
    1. File exists and is parseable
    2. Session is not older than max_age_hours
    3. Has expected cookies
    """
    if max_age_hours is None:
        max_age_hours = settings.browser_session_max_age_hours

    if not storage_path.exists():
        return False

    try:
        mtime = datetime.fromtimestamp(storage_path.stat().st_mtime)
        if datetime.now() - mtime > timedelta(hours=max_age_hours):
            return False

        with open(storage_path) as f:
            state = json.load(f)
            cookies = state.get("cookies", [])
            return len(cookies) > 0

    except (json.JSONDecodeError, OSError, KeyError):
        return False


def get_session_info(storage_path: Path) -> dict | None:
    """Get information about a stored session."""
    if not storage_path.exists():
        return None

    try:
        mtime = datetime.fromtimestamp(storage_path.stat().st_mtime)
        with open(storage_path) as f:
            state = json.load(f)

        return {
            "last_modified": mtime.isoformat(),
            "age_hours": get_session_age_hours(storage_path),
            "cookie_count": len(state.get("cookies", [])),
            "has_local_storage": len(state.get("origins", [])) > 0,
        }
    except (json.JSONDecodeError, OSError):
        return None
