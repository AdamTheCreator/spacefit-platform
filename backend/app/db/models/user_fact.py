"""User-level personal facts learned from chats.

A row represents a single durable assertion about a user (e.g. "prefers
Texas multifamily, $5-15M deals") in one of four lifecycle states:

  pending   — extracted by the AI, not yet reviewed by the user.
  approved  — confirmed by the user; eligible for system-prompt injection.
  rejected  — user said no; never re-extracted from the source turn.
  archived  — user dismissed an old approved fact.

Approval is required before a fact is injected into the prompt, matching
the "auto-extract with user approval" choice in the design spec.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def utc_now() -> datetime:
    return datetime.utcnow()


def uuid_str() -> str:
    return str(uuid.uuid4())


class UserFact(Base):
    __tablename__ = "user_facts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    text: Mapped[str] = mapped_column(Text, nullable=False)
    # Lightweight bucket used by the UI to group facts; not constrained
    # in code so the extractor can return whatever shape the prompt
    # produces. Recognized values: deal_prefs | geography | business_model
    # | personal | other.
    category: Mapped[str] = mapped_column(String(40), default="other", nullable=False)

    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=0.5, nullable=False)

    source_session_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("chat_sessions.id", ondelete="SET NULL"),
        nullable=True,
    )
    source_message_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("chat_messages.id", ondelete="SET NULL"),
        nullable=True,
    )

    approved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utc_now, onupdate=utc_now
    )

    user = relationship("User", back_populates=None)
