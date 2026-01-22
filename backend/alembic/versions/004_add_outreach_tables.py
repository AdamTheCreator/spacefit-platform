"""Add outreach campaign tables

Revision ID: 004
Revises: 003
Create Date: 2025-01-22
"""

from alembic import op
import sqlalchemy as sa

revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None


def upgrade():
    # Create outreach_campaigns table
    op.create_table(
        "outreach_campaigns",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # Campaign details
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("property_address", sa.Text, nullable=False),
        sa.Column("property_name", sa.String(200), nullable=True),
        # Email content
        sa.Column("subject", sa.String(500), nullable=False),
        sa.Column("body_template", sa.Text, nullable=False),
        # Sender info
        sa.Column("from_name", sa.String(200), nullable=False),
        sa.Column("from_email", sa.String(200), nullable=False),
        sa.Column("reply_to", sa.String(200), nullable=True),
        # Status tracking
        sa.Column("status", sa.String(20), server_default="draft"),
        # Timing
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("scheduled_at", sa.DateTime, nullable=True),
        sa.Column("sent_at", sa.DateTime, nullable=True),
        sa.Column("completed_at", sa.DateTime, nullable=True),
        # Stats
        sa.Column("total_recipients", sa.Integer, server_default="0"),
        sa.Column("sent_count", sa.Integer, server_default="0"),
        sa.Column("delivered_count", sa.Integer, server_default="0"),
        sa.Column("opened_count", sa.Integer, server_default="0"),
        sa.Column("clicked_count", sa.Integer, server_default="0"),
        sa.Column("replied_count", sa.Integer, server_default="0"),
        sa.Column("bounced_count", sa.Integer, server_default="0"),
        # Source data
        sa.Column("void_analysis_id", sa.String(36), nullable=True),
        sa.Column("session_id", sa.String(36), nullable=True),
    )
    op.create_index("ix_outreach_campaigns_user_id", "outreach_campaigns", ["user_id"])
    op.create_index("ix_outreach_campaigns_status", "outreach_campaigns", ["status"])

    # Create outreach_recipients table
    op.create_table(
        "outreach_recipients",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "campaign_id",
            sa.String(36),
            sa.ForeignKey("outreach_campaigns.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # Recipient info
        sa.Column("tenant_name", sa.String(200), nullable=False),
        sa.Column("contact_email", sa.String(200), nullable=False),
        sa.Column("contact_name", sa.String(200), nullable=True),
        sa.Column("contact_title", sa.String(100), nullable=True),
        # Void analysis context
        sa.Column("category", sa.String(100), nullable=True),
        sa.Column("match_score", sa.Float, nullable=True),
        sa.Column("nearest_location", sa.String(200), nullable=True),
        sa.Column("distance_miles", sa.Float, nullable=True),
        # Status tracking
        sa.Column("status", sa.String(20), server_default="pending"),
        # Timing
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("sent_at", sa.DateTime, nullable=True),
        sa.Column("delivered_at", sa.DateTime, nullable=True),
        sa.Column("opened_at", sa.DateTime, nullable=True),
        sa.Column("clicked_at", sa.DateTime, nullable=True),
        sa.Column("replied_at", sa.DateTime, nullable=True),
        # Error tracking
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("bounce_reason", sa.Text, nullable=True),
        # Email content (stored after sending)
        sa.Column("email_subject", sa.String(500), nullable=True),
        sa.Column("email_body", sa.Text, nullable=True),
        # Notes and exclusion
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("is_excluded", sa.Boolean, server_default="0"),
        # Tracking IDs for open/click tracking
        sa.Column("tracking_id", sa.String(36), nullable=True),
    )
    op.create_index(
        "ix_outreach_recipients_campaign_id", "outreach_recipients", ["campaign_id"]
    )
    op.create_index("ix_outreach_recipients_status", "outreach_recipients", ["status"])
    op.create_index(
        "ix_outreach_recipients_tracking_id", "outreach_recipients", ["tracking_id"]
    )

    # Create outreach_templates table
    op.create_table(
        "outreach_templates",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("subject_template", sa.String(500), nullable=False),
        sa.Column("body_template", sa.Text, nullable=False),
        sa.Column("category", sa.String(50), nullable=True),
        sa.Column("times_used", sa.Integer, server_default="0"),
        sa.Column("last_used_at", sa.DateTime, nullable=True),
        sa.Column("is_default", sa.Boolean, server_default="0"),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_outreach_templates_user_id", "outreach_templates", ["user_id"])


def downgrade():
    op.drop_index("ix_outreach_templates_user_id", "outreach_templates")
    op.drop_table("outreach_templates")

    op.drop_index("ix_outreach_recipients_tracking_id", "outreach_recipients")
    op.drop_index("ix_outreach_recipients_status", "outreach_recipients")
    op.drop_index("ix_outreach_recipients_campaign_id", "outreach_recipients")
    op.drop_table("outreach_recipients")

    op.drop_index("ix_outreach_campaigns_status", "outreach_campaigns")
    op.drop_index("ix_outreach_campaigns_user_id", "outreach_campaigns")
    op.drop_table("outreach_campaigns")
