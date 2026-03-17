"""
Project model — bundles documents + chats + instructions around a single property.
"""
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models.chat import ChatSession
    from app.db.models.deal import Property
    from app.db.models.document import ParsedDocument
    from app.db.models.user import User


def utc_now() -> datetime:
    return datetime.utcnow()


def uuid_str() -> str:
    return str(uuid.uuid4())


class Project(Base):
    """
    A project groups documents, chat sessions, and custom instructions
    around a single property for focused analysis.
    """
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    property_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("properties.id", ondelete="SET NULL"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    instructions: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now)

    # Relationships
    user: Mapped["User"] = relationship(back_populates="projects")
    property: Mapped["Property | None"] = relationship(back_populates="projects")
    documents: Mapped[list["ParsedDocument"]] = relationship(
        back_populates="project", order_by="ParsedDocument.created_at.desc()"
    )
    sessions: Mapped[list["ChatSession"]] = relationship(
        back_populates="project", order_by="ChatSession.updated_at.desc()"
    )
