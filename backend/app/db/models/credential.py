import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, LargeBinary
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def utc_now() -> datetime:
    return datetime.utcnow()


def uuid_str() -> str:
    return str(uuid.uuid4())


class SiteCredential(Base):
    __tablename__ = "site_credentials"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    site_name: Mapped[str] = mapped_column(String(100), nullable=False)
    site_url: Mapped[str] = mapped_column(Text, nullable=False)
    username_encrypted: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    password_encrypted: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    additional_config_encrypted: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    last_verified_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now)

    # Session tracking for browser automation
    session_status: Mapped[str] = mapped_column(
        String(20), default="unknown"
    )  # unknown, valid, expired, error
    session_last_checked: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    session_error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Usage tracking
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    total_uses: Mapped[int] = mapped_column(Integer, default=0)

    # Connector health state machine
    connector_status: Mapped[str] = mapped_column(
        String(20), default="stale"
    )  # connected, stale, needs_reauth, degraded, error, disabled
    health_meta: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON blob
    last_probe_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    disabled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    disabled_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    user: Mapped["User"] = relationship(back_populates="site_credentials")
    agent_connections: Mapped[list["AgentConnection"]] = relationship(back_populates="credential")


class AgentConnection(Base):
    __tablename__ = "agent_connections"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    credential_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("site_credentials.id", ondelete="SET NULL"), nullable=True
    )
    agent_type: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="disconnected")
    last_connected_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now)

    credential: Mapped["SiteCredential | None"] = relationship(back_populates="agent_connections")


class OnboardingProgress(Base):
    __tablename__ = "onboarding_progress"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    current_step: Mapped[int] = mapped_column(Integer, default=0)
    completed_steps: Mapped[str | None] = mapped_column(Text, default="[]")
    skipped_steps: Mapped[str | None] = mapped_column(Text, default="[]")
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now)

    user: Mapped["User"] = relationship(back_populates="onboarding_progress")


class UserPreferences(Base):
    """
    User preferences for personalizing the AI assistant behavior.
    These preferences are used to customize the system prompt and agent priorities.
    """
    __tablename__ = "user_preferences"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True
    )

    # Professional Role
    role: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # Options: broker, landlord, investor, developer, analyst, other

    # Property Type Focus (JSON array)
    property_types: Mapped[str | None] = mapped_column(Text, nullable=True, default="[]")
    # Options: retail, industrial, office, mixed_use, multifamily

    # Tenant Category Focus (JSON array)
    tenant_categories: Mapped[str | None] = mapped_column(Text, nullable=True, default="[]")
    # Options: qsr, casual_dining, fitness, medical, apparel, grocery,
    #          convenience, banking, services, entertainment, etc.

    # Geographic Markets (JSON array)
    markets: Mapped[str | None] = mapped_column(Text, nullable=True, default="[]")
    # Free-form: ["Fairfield County, CT", "Westchester, NY", etc.]

    # Deal Size Range
    deal_size_min: Mapped[int | None] = mapped_column(Integer, nullable=True)  # in SF
    deal_size_max: Mapped[int | None] = mapped_column(Integer, nullable=True)  # in SF

    # Key Tenant Relationships (JSON array of tenant names)
    key_tenants: Mapped[str | None] = mapped_column(Text, nullable=True, default="[]")
    # Free-form: ["Chick-fil-A", "Chipotle", "Planet Fitness", etc.]

    # Analysis Priorities (JSON array)
    analysis_priorities: Mapped[str | None] = mapped_column(Text, nullable=True, default="[]")
    # Options: traffic_counts, demographics, void_analysis, competition, visibility

    # Custom Notes (free-form text for additional context)
    custom_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Profile completion tracking
    is_complete: Mapped[bool] = mapped_column(Boolean, default=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now)

    user: Mapped["User"] = relationship(back_populates="preferences")


from app.db.models.user import User  # noqa: E402
