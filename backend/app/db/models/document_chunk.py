"""Indexed text chunks of a parsed document.

Each row holds a ~800-token slice of a ``ParsedDocument`` together with
a Postgres ``tsvector`` (defined as a generated column at the SQL level
— see migration 034) so the chat can do keyword search via the
``document_search`` MCP tool.

``user_id`` + ``project_id`` are denormalized for cheap scope filtering;
this keeps the auth check on the tool a single index lookup instead of
two joins back through ``parsed_documents``.

``embedding`` is a ``LargeBinary`` placeholder so a future migration can
``ALTER COLUMN ... TYPE vector(N)`` without touching the rest of the
schema.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Computed,
    DateTime,
    ForeignKey,
    Integer,
    LargeBinary,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models.document import ParsedDocument


def utc_now() -> datetime:
    return datetime.utcnow()


def uuid_str() -> str:
    return str(uuid.uuid4())


class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    document_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("parsed_documents.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    project_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("projects.id", ondelete="SET NULL"),
        nullable=True,
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    token_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # See module docstring: BYTEA placeholder for pgvector.
    embedding: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)

    # Generated tsvector column — populated by Postgres from ``text``.
    # Declared as a SQLAlchemy generated column so ORM queries can filter
    # against it via ``search_vector.op('@@')(...)``. Read-only on the ORM
    # side: alembic creates the underlying ``GENERATED ALWAYS AS ... STORED``
    # column in migration 034.
    search_vector: Mapped[str | None] = mapped_column(
        TSVECTOR,
        Computed("to_tsvector('english', coalesce(text, ''))", persisted=True),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)

    document: Mapped["ParsedDocument"] = relationship()
