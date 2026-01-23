import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def utc_now() -> datetime:
    return datetime.utcnow()


def uuid_str() -> str:
    return str(uuid.uuid4())


class SubscriptionTier(str, enum.Enum):
    FREE = "free"
    PRO = "pro"
    ENTERPRISE = "enterprise"


class SubscriptionStatus(str, enum.Enum):
    ACTIVE = "active"
    CANCELED = "canceled"
    PAST_DUE = "past_due"
    TRIALING = "trialing"
    PAUSED = "paused"


class SubscriptionPlan(Base):
    """Available subscription plans with their limits and pricing."""

    __tablename__ = "subscription_plans"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    tier: Mapped[SubscriptionTier] = mapped_column(
        Enum(SubscriptionTier), unique=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Pricing
    price_monthly: Mapped[int] = mapped_column(Integer, default=0)  # In cents
    stripe_price_id: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Feature limits (-1 = unlimited)
    chat_sessions_per_month: Mapped[int] = mapped_column(Integer, default=10)
    void_analyses_per_month: Mapped[int] = mapped_column(Integer, default=3)
    demographics_reports_per_month: Mapped[int] = mapped_column(Integer, default=5)
    emails_per_month: Mapped[int] = mapped_column(Integer, default=0)
    documents_per_month: Mapped[int] = mapped_column(Integer, default=5)
    team_members: Mapped[int] = mapped_column(Integer, default=1)

    # Feature flags
    has_placer_access: Mapped[bool] = mapped_column(Boolean, default=False)
    has_siteusa_access: Mapped[bool] = mapped_column(Boolean, default=False)
    has_costar_access: Mapped[bool] = mapped_column(Boolean, default=False)
    has_email_outreach: Mapped[bool] = mapped_column(Boolean, default=False)
    has_api_access: Mapped[bool] = mapped_column(Boolean, default=False)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)

    # Relationships
    subscriptions: Mapped[list["Subscription"]] = relationship(
        back_populates="plan", cascade="all, delete-orphan"
    )


class Subscription(Base):
    """User's active subscription."""

    __tablename__ = "subscriptions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    plan_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("subscription_plans.id"), nullable=False
    )
    status: Mapped[SubscriptionStatus] = mapped_column(
        Enum(SubscriptionStatus), default=SubscriptionStatus.ACTIVE
    )

    # Stripe integration
    stripe_customer_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    stripe_subscription_id: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Billing cycle
    current_period_start: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    current_period_end: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    cancel_at_period_end: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now)

    # Relationships
    user: Mapped["User"] = relationship(back_populates="subscription")
    plan: Mapped["SubscriptionPlan"] = relationship(back_populates="subscriptions")
    usage_records: Mapped[list["UsageRecord"]] = relationship(
        back_populates="subscription", cascade="all, delete-orphan"
    )


class UsageType(str, enum.Enum):
    CHAT_SESSION = "chat_session"
    VOID_ANALYSIS = "void_analysis"
    DEMOGRAPHICS_REPORT = "demographics_report"
    EMAIL_SENT = "email_sent"
    DOCUMENT_PARSED = "document_parsed"


class UsageRecord(Base):
    """Track usage per user per billing period."""

    __tablename__ = "usage_records"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    subscription_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("subscriptions.id", ondelete="CASCADE"), nullable=False
    )
    usage_type: Mapped[UsageType] = mapped_column(Enum(UsageType), nullable=False)
    count: Mapped[int] = mapped_column(Integer, default=0)

    # Period tracking (reset monthly)
    period_start: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    period_end: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now)

    # Relationships
    subscription: Mapped["Subscription"] = relationship(back_populates="usage_records")


# Forward reference
from app.db.models.user import User  # noqa: E402
