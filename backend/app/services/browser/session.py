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

        cookies = state.get("cookies", [])

        # Check for authentication cookies (site-specific)
        has_auth_cookie = any(
            c.get("name") in ("login", "auth", "session", "token", "jwt", "_session")
            or "auth" in c.get("name", "").lower()
            or "login" in c.get("name", "").lower()
            or "session" in c.get("name", "").lower()
            for c in cookies
        )

        return {
            "last_modified": mtime.isoformat(),
            "age_hours": get_session_age_hours(storage_path),
            "cookie_count": len(cookies),
            "has_local_storage": len(state.get("origins", [])) > 0,
            "has_auth_cookie": has_auth_cookie,
        }
    except (json.JSONDecodeError, OSError):
        return None


def has_valid_auth_session(storage_path: Path, site_name: str) -> bool:
    """
    Check if a session file contains valid authentication cookies.

    This is a more thorough check than is_session_valid() as it looks
    for site-specific authentication indicators.
    """
    if not is_session_valid(storage_path):
        return False

    info = get_session_info(storage_path)
    if info is None:
        return False

    # Site-specific authentication cookie checks
    site_auth_indicators = {
        "placer": ["login", "placer"],  # Placer.ai uses "login" cookie
        "siteusa": ["session", "regis"],  # SiteUSA REGIS session cookies
        "costar": ["costar", "session"],  # CoStar session cookies
    }

    try:
        with open(storage_path) as f:
            state = json.load(f)

        cookies = state.get("cookies", [])
        site_key = site_name.lower()

        if site_key in site_auth_indicators:
            indicators = site_auth_indicators[site_key]
            for cookie in cookies:
                cookie_name = cookie.get("name", "").lower()
                for indicator in indicators:
                    if indicator in cookie_name:
                        return True
            return False

        # For unknown sites, just check if there are any auth-looking cookies
        return info.get("has_auth_cookie", False)

    except (json.JSONDecodeError, OSError):
        return False


def get_session_status_for_site(
    storage_path: Path,
    site_name: str,
    requires_manual_login: bool = False,
) -> dict:
    """
    Get detailed session status for a site.

    Returns a dict with:
    - status: "valid", "expired", "no_session", "needs_refresh"
    - message: Human-readable status message
    - details: Additional info (age, cookie count, etc.)
    """
    if not storage_path.exists():
        if requires_manual_login:
            return {
                "status": "needs_manual_login",
                "message": "No session found. This site requires manual login to solve CAPTCHA.",
                "details": None,
            }
        return {
            "status": "no_session",
            "message": "No session found",
            "details": None,
        }

    info = get_session_info(storage_path)
    if info is None:
        return {
            "status": "corrupted",
            "message": "Session file is corrupted or unreadable",
            "details": None,
        }

    age_hours = info.get("age_hours", 0)
    max_age = settings.browser_session_max_age_hours

    # Check if session is expired by age
    if age_hours > max_age:
        if requires_manual_login:
            return {
                "status": "expired_needs_manual",
                "message": f"Session expired ({age_hours:.1f}h old). This site requires manual login to refresh.",
                "details": info,
            }
        return {
            "status": "expired",
            "message": f"Session expired ({age_hours:.1f}h old, max {max_age}h)",
            "details": info,
        }

    # Check for auth cookies
    if not has_valid_auth_session(storage_path, site_name):
        if requires_manual_login:
            return {
                "status": "invalid_needs_manual",
                "message": "Session file exists but lacks authentication cookies. Manual login required.",
                "details": info,
            }
        return {
            "status": "invalid",
            "message": "Session file exists but lacks authentication cookies",
            "details": info,
        }

    # Session looks valid
    hours_remaining = max_age - age_hours
    return {
        "status": "valid",
        "message": f"Session valid ({hours_remaining:.1f}h remaining)",
        "details": info,
    }
