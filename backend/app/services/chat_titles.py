"""Helpers for chat session titles."""
from __future__ import annotations

from app.db.models.chat import ChatSession


def fallback_title_from_message(content: str, max_len: int = 60) -> str:
    """Collapse whitespace and truncate a user message for use as a title."""
    cleaned = " ".join(content.strip().split())
    if not cleaned:
        return ""
    if len(cleaned) <= max_len:
        return cleaned
    return cleaned[: max_len - 1].rstrip() + "…"


def backfill_session_title(session: ChatSession) -> bool:
    # Covers sessions created before title generation wired up and sessions
    # where the LLM title call raised (the orchestrator swallows those). Without
    # this the list view shows "New conversation" forever.
    if session.title:
        return False
    first_user = next(
        (m for m in session.messages if m.role == "user"),
        None,
    )
    if first_user is None:
        return False
    title = fallback_title_from_message(first_user.content)
    if not title:
        return False
    session.title = title
    return True
