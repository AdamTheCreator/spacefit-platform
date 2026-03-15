import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import DateTime, ForeignKey, String, Text, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def uuid_str() -> str:
    return str(uuid.uuid4())


def default_expiry() -> datetime:
    return datetime.now(timezone.utc) + timedelta(days=30)


class SharedReport(Base):
    __tablename__ = "shared_reports"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    session_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    share_token: Mapped[str] = mapped_column(String(36), unique=True, default=uuid_str)
    report_type: Mapped[str] = mapped_column(String(50), nullable=False)  # demographics, tenant_mix, comprehensive
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    content_snapshot: Mapped[str | None] = mapped_column(Text, nullable=True)  # Markdown snapshot of the report
    view_count: Mapped[int] = mapped_column(Integer, default=0)
    expires_at: Mapped[datetime] = mapped_column(DateTime, default=default_expiry)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
