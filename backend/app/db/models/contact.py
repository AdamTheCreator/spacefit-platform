"""Contacts directory — companies (brands / clients), their people, and a
per-contact interaction timeline.

Real, per-user replacement for the old hardcoded frontend mock directory. Each
company carries the explicit tenant/expansion criteria the directory UI shows
(sector, SF range, target markets, expanding flag) plus a flexible ``criteria``
JSON "buy box" that the future client-fit Search engine will score against.
``user_id`` is denormalized onto every row so auth + scope filters are a single
indexed lookup rather than a join.
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def utc_now() -> datetime:
    return datetime.utcnow()


def uuid_str() -> str:
    return str(uuid.uuid4())


class Company(Base):
    """A brand / client tracked in the contacts directory."""

    __tablename__ = "companies"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    sector: Mapped[str | None] = mapped_column(String(100), nullable=True)
    subsector: Mapped[str | None] = mapped_column(String(100), nullable=True)
    us_locations: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_expanding: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    # list[str] of target market labels, e.g. ["NY", "NJ", "Northeast"]
    target_markets: Mapped[list | None] = mapped_column(JSON, nullable=True)
    sf_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sf_max: Mapped[int | None] = mapped_column(Integer, nullable=True)
    website: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Forward-compatible acquisition "buy box" for the client-fit Search engine:
    # {asset_types, budget_min, budget_max, cap_rate_max, geographies, free_form}
    criteria: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    enriched_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utc_now, onupdate=utc_now
    )

    contacts: Mapped[list["Contact"]] = relationship(
        back_populates="company", cascade="all, delete-orphan"
    )


class Contact(Base):
    """A person at a company."""

    __tablename__ = "contacts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    company_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    first: Mapped[str] = mapped_column(String(100), nullable=False)
    last: Mapped[str | None] = mapped_column(String(100), nullable=True)
    role: Mapped[str | None] = mapped_column(String(150), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Stored as plain strings (not native PG enums) and validated in Pydantic.
    # verif:  verified | unverified | stale | bounced
    verif: Mapped[str] = mapped_column(String(20), default="unverified")
    # source: apollo | linkedin | costar_import | manual
    source: Mapped[str] = mapped_column(String(30), default="manual")
    linkedin: Mapped[bool] = mapped_column(Boolean, default=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    last_verified_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_contacted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_reply_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utc_now, onupdate=utc_now
    )

    company: Mapped["Company"] = relationship(back_populates="contacts")
    interactions: Mapped[list["ContactInteraction"]] = relationship(
        back_populates="contact", cascade="all, delete-orphan"
    )


class ContactInteraction(Base):
    """A timeline event (note, meeting, enrichment, email) for a contact."""

    __tablename__ = "contact_interactions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    contact_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("contacts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # type: meeting | note | enrich | email_in | email_out
    type: Mapped[str] = mapped_column(String(20), default="note")
    occurred_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    who: Mapped[str | None] = mapped_column(String(150), nullable=True)
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    summary: Mapped[str] = mapped_column(Text, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)

    contact: Mapped["Contact"] = relationship(back_populates="interactions")
