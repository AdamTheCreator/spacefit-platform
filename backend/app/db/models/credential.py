import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Identity,
    Integer,
    LargeBinary,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


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


class UserAIConfig(Base):
    """Per-user AI provider configuration for BYOK (Bring Your Own Key).

    One row represents one credential in its lifecycle. A user can have at
    most one row in status ``active`` or ``rotating`` per provider (enforced
    by the partial unique index in migration 028); revoked/invalid rows are
    retained for audit. The credential_audit_log table records access to
    these rows.
    """
    __tablename__ = "user_ai_configs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )

    # Org-ready. scope_level='user' for every current row; org_id stays NULL
    # until organizations exist. Resolution code filters scope_level='user'
    # today; when orgs land, it will add a fallback to scope_level='org'.
    scope_level: Mapped[str] = mapped_column(String(10), default="user", nullable=False)
    org_id: Mapped[str | None] = mapped_column(String(36), nullable=True)

    # Provider selection. Legal values validated in application code — kept
    # as a String column rather than Enum to keep migrations simple (adding
    # a new provider is additive in code, no schema change).
    provider: Mapped[str] = mapped_column(String(30), default="platform_default")

    # Model override.
    model: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Envelope-encrypted key material. After migration 029 backfill, the
    # invariant for an ``active`` row is:
    #   api_key_encrypted = AES-256-GCM(dek, ciphertext_iv, api_key) + tag
    #   ciphertext_tag    = GCM auth tag for api_key_encrypted
    #   encrypted_dek     = KEK-wrapped DEK
    #   kek_id            = identifier of the KEK that wrapped the DEK
    # For a revoked row, all four are zeroed (crypto-shredded).
    api_key_encrypted: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    ciphertext_iv: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    ciphertext_tag: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    encrypted_dek: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    kek_id: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Legacy Fernet column, retained during the 029→030 migration window so
    # rollback is possible; drop in migration 030 after envelope is stable.
    encryption_salt: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)

    # Display + dedupe.
    key_fingerprint: Mapped[str | None] = mapped_column(String(64), nullable=True)
    key_last_four: Mapped[str | None] = mapped_column(String(8), nullable=True)
    label: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Custom endpoint for DeepSeek, local LLMs, OpenAI-compatible gateways.
    base_url: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Per-specialist model overrides (JSON):
    # {"orchestrator": "claude-sonnet-4-6-...", "scout": "claude-haiku-4-5-...", ...}
    specialist_models_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Governance scope (JSON). Recognized keys:
    #   allowed_models: list[str]
    #   denied_models: list[str]
    #   monthly_spend_cap_usd: number
    #   monthly_request_cap: int
    scope: Mapped[str] = mapped_column(Text, default="{}", nullable=False)

    # Lifecycle: active | rotating | invalid | revoked. Enforcement of the
    # "at most one active|rotating per (user_id, provider)" invariant is at
    # the DB level via a partial unique index.
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)

    # Validation status (live-call provider check).
    is_key_valid: Mapped[bool] = mapped_column(Boolean, default=False)
    key_validated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    key_error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Audit timestamps. last_used_at is async-updated post-request; created_by
    # is the acting user (may differ from user_id when admin creates on their
    # behalf); revoked_* are set on soft-delete.
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    revoked_by: Mapped[str | None] = mapped_column(String(36), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now)

    user: Mapped["User"] = relationship(back_populates="ai_configs")


class CredentialAuditLog(Base):
    """Append-only audit trail for every BYOK credential action.

    Written by ``app.byok.audit`` on every create / validate / use / rotate /
    revoke. Survives credential deletion (credential_id becomes NULL, the
    fingerprint column preserves the logical linkage).
    """
    __tablename__ = "credential_audit_log"

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=False), primary_key=True)
    credential_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("user_ai_configs.id", ondelete="SET NULL"),
        nullable=True,
    )
    credential_fingerprint: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    actor_user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    provider: Mapped[str | None] = mapped_column(String(30), nullable=True)
    request_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    success: Mapped[bool] = mapped_column(Boolean, nullable=False)
    error_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    metadata_json: Mapped[str] = mapped_column(Text, default="{}", nullable=False)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)


from app.db.models.user import User  # noqa: E402
