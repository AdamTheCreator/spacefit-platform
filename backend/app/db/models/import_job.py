"""ImportJob model — tracks user-uploaded CSV/PDF imports, optionally scoped to a Project."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def uuid_str() -> str:
    return str(uuid.uuid4())


class ImportJob(Base):
    __tablename__ = "import_jobs"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=uuid_str
    )
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    # Project scoping — NULL means library-level (reusable across projects)
    project_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("projects.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )
    source: Mapped[str] = mapped_column(
        String(32), nullable=False,
    )  # "costar" | "placer" | "siteusa"
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="parsing",
    )  # "parsing" | "ready" | "error"
    original_filename: Mapped[str] = mapped_column(
        String(500), nullable=False,
    )
    parsed_payload_json: Mapped[str | None] = mapped_column(
        Text, nullable=True,
    )
    error_message: Mapped[str | None] = mapped_column(
        Text, nullable=True,
    )
    record_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=utc_now, index=True,
    )
