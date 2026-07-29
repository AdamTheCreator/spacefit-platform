import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def utc_now() -> datetime:
    return datetime.utcnow()


def uuid_str() -> str:
    return str(uuid.uuid4())


# Canonical auth event names. Kept as plain strings (VARCHAR column, not a
# native PG enum) per the repo's enum convention.
EVENT_LOGIN = "login"
EVENT_LOGIN_FAILED = "login_failed"
EVENT_RESET_REQUESTED = "reset_requested"
EVENT_RESET_COMPLETED = "reset_completed"
EVENT_PASSWORD_CHANGED = "password_changed"
EVENT_EMAIL_VERIFIED = "email_verified"
EVENT_ACCOUNT_LOCKED = "account_locked"
EVENT_REFRESH_REUSE = "refresh_reuse_detected"


class AuthEvent(Base):
    """Append-only audit log of authentication events.

    NEVER stores passwords, tokens, or reset links. ``user_id`` is nullable
    because failed logins / reset requests for unknown emails have no user.
    """

    __tablename__ = "auth_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    event: Mapped[str] = mapped_column(String(40), nullable=False)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)
    request_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)

    __table_args__ = (
        Index("ix_auth_events_user_id", "user_id"),
        Index("ix_auth_events_event", "event"),
        Index("ix_auth_events_created_at", "created_at"),
    )
