"""Property listings — imported CRE deals scored against a client's buy-box.

The inverse of the void/matchmaker flow: instead of finding tenants for a
vacancy, the client-fit engine imports for-sale property listings and ranks
them against a ``Company``'s acquisition criteria (the "buy box"). Listings are
per-user; ``user_id`` is denormalized onto every row so auth + scope filters
are a single indexed lookup rather than a join.
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    JSON,
    BigInteger,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def utc_now() -> datetime:
    return datetime.utcnow()


def uuid_str() -> str:
    return str(uuid.uuid4())


class PropertyListing(Base):
    """A for-sale CRE property listing imported by a user."""

    __tablename__ = "property_listings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    city: Mapped[str | None] = mapped_column(String(255), nullable=True)
    state: Mapped[str | None] = mapped_column(String(255), nullable=True)
    zip_code: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # Plain string (not native PG enum): retail | office | industrial |
    # multifamily | mixed-use | land
    asset_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    size_sf: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Whole dollars; BigInteger so 9-figure asking prices don't overflow.
    price: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    cap_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    year_built: Mapped[int | None] = mapped_column(Integer, nullable=True)
    units: Mapped[int | None] = mapped_column(Integer, nullable=True)
    listing_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Plain string (not native PG enum): csv | xlsx | manual | costar | ...
    source: Mapped[str] = mapped_column(String(50), default="csv")
    # Original import row, kept verbatim for re-mapping / debugging.
    raw: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utc_now, onupdate=utc_now
    )
