"""
Outreach Campaign Models

Database models for email blast campaigns to tenants based on void analysis.
This replaces the manual spreadsheet + mail merge workflow.
"""

import uuid
from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, Float
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def uuid_str() -> str:
    return str(uuid.uuid4())


class CampaignStatus(str, Enum):
    DRAFT = "draft"
    SCHEDULED = "scheduled"
    SENDING = "sending"
    SENT = "sent"
    CANCELLED = "cancelled"


class RecipientStatus(str, Enum):
    PENDING = "pending"
    SENT = "sent"
    DELIVERED = "delivered"
    OPENED = "opened"
    CLICKED = "clicked"
    REPLIED = "replied"
    BOUNCED = "bounced"
    UNSUBSCRIBED = "unsubscribed"


class OutreachCampaign(Base):
    """
    An email outreach campaign targeting tenants based on void analysis.

    Workflow:
    1. User runs void analysis for a property
    2. AI identifies target tenants with contacts
    3. User reviews and approves recipient list
    4. Campaign is created with customizable template
    5. Emails are sent in batches
    """
    __tablename__ = "outreach_campaigns"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )

    # Campaign details
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    property_address: Mapped[str] = mapped_column(Text, nullable=False)
    property_name: Mapped[str | None] = mapped_column(String(200), nullable=True)

    # Email content
    subject: Mapped[str] = mapped_column(String(500), nullable=False)
    body_template: Mapped[str] = mapped_column(Text, nullable=False)
    # Template supports placeholders: {{tenant_name}}, {{property_name}}, {{property_address}}
    # {{user_name}}, {{user_email}}, {{user_phone}}

    # Sender info (from user profile)
    from_name: Mapped[str] = mapped_column(String(200), nullable=False)
    from_email: Mapped[str] = mapped_column(String(200), nullable=False)
    reply_to: Mapped[str | None] = mapped_column(String(200), nullable=True)

    # Status tracking
    status: Mapped[str] = mapped_column(String(20), default=CampaignStatus.DRAFT.value)

    # Timing
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now)
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Stats (updated as emails are sent)
    total_recipients: Mapped[int] = mapped_column(Integer, default=0)
    sent_count: Mapped[int] = mapped_column(Integer, default=0)
    delivered_count: Mapped[int] = mapped_column(Integer, default=0)
    opened_count: Mapped[int] = mapped_column(Integer, default=0)
    clicked_count: Mapped[int] = mapped_column(Integer, default=0)
    replied_count: Mapped[int] = mapped_column(Integer, default=0)
    bounced_count: Mapped[int] = mapped_column(Integer, default=0)

    # Source data (for reference)
    void_analysis_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    session_id: Mapped[str | None] = mapped_column(String(36), nullable=True)  # Chat session where this was created

    # Relationships
    recipients: Mapped[list["OutreachRecipient"]] = relationship(
        back_populates="campaign", cascade="all, delete-orphan"
    )


class OutreachRecipient(Base):
    """
    A recipient of an outreach campaign.

    Created from void analysis results with tenant contact info.
    """
    __tablename__ = "outreach_recipients"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    campaign_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("outreach_campaigns.id", ondelete="CASCADE"), nullable=False
    )

    # Recipient info
    tenant_name: Mapped[str] = mapped_column(String(200), nullable=False)
    contact_email: Mapped[str] = mapped_column(String(200), nullable=False)
    contact_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    contact_title: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Void analysis context
    category: Mapped[str | None] = mapped_column(String(100), nullable=True)  # e.g., "Fast Casual", "Coffee"
    match_score: Mapped[float | None] = mapped_column(Float, nullable=True)  # 0-100
    nearest_location: Mapped[str | None] = mapped_column(String(200), nullable=True)
    distance_miles: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Status tracking
    status: Mapped[str] = mapped_column(String(20), default=RecipientStatus.PENDING.value)

    # Timing
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    opened_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    clicked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    replied_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Error tracking
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    bounce_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    # The actual email sent (for records)
    email_subject: Mapped[str | None] = mapped_column(String(500), nullable=True)
    email_body: Mapped[str | None] = mapped_column(Text, nullable=True)

    # User can add notes
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Exclusion flag (user can exclude specific recipients)
    is_excluded: Mapped[bool] = mapped_column(Boolean, default=False)

    # Relationships
    campaign: Mapped["OutreachCampaign"] = relationship(back_populates="recipients")


class OutreachTemplate(Base):
    """
    Saved email templates for reuse across campaigns.
    """
    __tablename__ = "outreach_templates"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    subject_template: Mapped[str] = mapped_column(String(500), nullable=False)
    body_template: Mapped[str] = mapped_column(Text, nullable=False)

    # Categorization
    category: Mapped[str | None] = mapped_column(String(50), nullable=True)  # e.g., "void_outreach", "follow_up"

    # Usage stats
    times_used: Mapped[int] = mapped_column(Integer, default=0)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    is_default: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now)
