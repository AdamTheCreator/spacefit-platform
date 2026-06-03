"""Outreach voice profiles — per-user prompts that put generated emails in
the broker's own voice.

A user can keep several named voices (e.g. "Warm intro", "Follow-up") and
mark one as the default. The AI email generator (``app.services.outreach_ai``)
injects the selected profile's ``instructions`` (+ optional ``sample`` and
``signature``) into the prompt so drafts read like the user wrote them.

``user_id`` is denormalized onto every row so the auth + scope filter is a
single indexed lookup rather than a join — same convention as listings and
contacts.
"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def utc_now() -> datetime:
    return datetime.utcnow()


def uuid_str() -> str:
    return str(uuid.uuid4())


class OutreachVoiceProfile(Base):
    """A reusable voice/tone prompt a user applies when drafting outreach."""

    __tablename__ = "outreach_voice_profiles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Short label shown in the picker, e.g. "Warm intro".
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    # The "write like me" prompt: tone, phrasing, do/don't, length, etc.
    instructions: Mapped[str] = mapped_column(Text, nullable=False)
    # Optional one-liner tone hint surfaced in the UI; not required for prompts.
    tone: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Optional real email the user wrote — used as a few-shot style anchor.
    sample: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Optional sign-off appended verbatim to the generated body.
    signature: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Exactly one row per user should carry True; enforced application-side.
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utc_now, onupdate=utc_now
    )
