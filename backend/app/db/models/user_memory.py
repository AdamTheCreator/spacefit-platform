"""
User Memory Model

Stores per-user context that persists across sessions:
- analyzed_properties: List of properties the user has analyzed
- book_of_business_summary: Summary of customer/tenant data
- preferences: Inferred user preferences from behavior
- ai_profile_summary: AI-written summary about the user
"""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def utc_now() -> datetime:
    return datetime.utcnow()


def uuid_str() -> str:
    return str(uuid.uuid4())


class UserMemory(Base):
    """
    Per-user memory that SpaceFit uses to personalize responses.

    Attributes:
        analyzed_properties: List of dicts with:
            - address: str
            - asset_type: str (e.g., "QSR pad", "Strip center")
            - analysis_date: str (ISO format)
            - key_findings: list[str]
            - void_count: int

        book_of_business_summary: Dict with:
            - tenant_count: int
            - top_categories: list[str]
            - coverage_areas: list[str]

        preferences: Dict with:
            - preferred_asset_types: list[str]
            - preferred_trade_areas: list[str]
            - typical_sf_range: dict with min/max

        ai_profile_summary: Text blob the AI writes summarizing the user
    """
    __tablename__ = "user_memory"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True
    )

    # List of analyzed properties with key findings
    analyzed_properties: Mapped[list] = mapped_column(JSONB, default=list)

    # Summary of the user's book of business (from customer imports)
    book_of_business_summary: Mapped[dict] = mapped_column(JSONB, default=dict)

    # Inferred preferences from behavior
    preferences: Mapped[dict] = mapped_column(JSONB, default=dict)

    # AI-generated profile summary
    ai_profile_summary: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Stats
    total_analyses: Mapped[int] = mapped_column(Integer, default=0)

    # Timestamps
    last_updated: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)

    # Relationship back to user
    user: Mapped["User"] = relationship(back_populates="memory")


# Forward reference
from app.db.models.user import User  # noqa: E402
