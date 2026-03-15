import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def uuid_str() -> str:
    return str(uuid.uuid4())


class TenantFeedback(Base):
    __tablename__ = "tenant_feedback"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    session_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    suggestion: Mapped[str] = mapped_column(Text, nullable=False)  # The tenant/brand suggested
    feedback: Mapped[str] = mapped_column(String(20), nullable=False)  # "positive" or "negative"
    correction_text: Mapped[str | None] = mapped_column(Text, nullable=True)  # User's correction note
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
