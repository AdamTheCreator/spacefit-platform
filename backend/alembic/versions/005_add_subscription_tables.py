"""Add subscription and billing tables

Revision ID: 005
Revises: 004
Create Date: 2026-01-22
"""

from alembic import op
import sqlalchemy as sa

revision = "005"
down_revision = "5c7681bfc694"
branch_labels = None
depends_on = None


def upgrade():
    # Create subscription_plans table
    op.create_table(
        "subscription_plans",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tier", sa.String(20), unique=True, nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        # Pricing
        sa.Column("price_monthly", sa.Integer, server_default="0"),
        sa.Column("stripe_price_id", sa.String(255), nullable=True),
        # Feature limits (-1 = unlimited)
        sa.Column("chat_sessions_per_month", sa.Integer, server_default="10"),
        sa.Column("void_analyses_per_month", sa.Integer, server_default="3"),
        sa.Column("demographics_reports_per_month", sa.Integer, server_default="5"),
        sa.Column("emails_per_month", sa.Integer, server_default="0"),
        sa.Column("documents_per_month", sa.Integer, server_default="5"),
        sa.Column("team_members", sa.Integer, server_default="1"),
        # Feature flags
        sa.Column("has_placer_access", sa.Boolean, server_default="0"),
        sa.Column("has_siteusa_access", sa.Boolean, server_default="0"),
        sa.Column("has_costar_access", sa.Boolean, server_default="0"),
        sa.Column("has_email_outreach", sa.Boolean, server_default="0"),
        sa.Column("has_api_access", sa.Boolean, server_default="0"),
        sa.Column("is_active", sa.Boolean, server_default="1"),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_subscription_plans_tier", "subscription_plans", ["tier"])

    # Create subscriptions table
    op.create_table(
        "subscriptions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            unique=True,
            nullable=False,
        ),
        sa.Column(
            "plan_id",
            sa.String(36),
            sa.ForeignKey("subscription_plans.id"),
            nullable=False,
        ),
        sa.Column("status", sa.String(20), server_default="active"),
        # Stripe integration
        sa.Column("stripe_customer_id", sa.String(255), nullable=True),
        sa.Column("stripe_subscription_id", sa.String(255), nullable=True),
        # Billing cycle
        sa.Column("current_period_start", sa.DateTime, nullable=True),
        sa.Column("current_period_end", sa.DateTime, nullable=True),
        sa.Column("cancel_at_period_end", sa.Boolean, server_default="0"),
        # Timestamps
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_subscriptions_user_id", "subscriptions", ["user_id"])
    op.create_index("ix_subscriptions_plan_id", "subscriptions", ["plan_id"])
    op.create_index(
        "ix_subscriptions_stripe_customer_id", "subscriptions", ["stripe_customer_id"]
    )
    op.create_index(
        "ix_subscriptions_stripe_subscription_id",
        "subscriptions",
        ["stripe_subscription_id"],
    )

    # Create usage_records table
    op.create_table(
        "usage_records",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "subscription_id",
            sa.String(36),
            sa.ForeignKey("subscriptions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("usage_type", sa.String(50), nullable=False),
        sa.Column("count", sa.Integer, server_default="0"),
        # Period tracking
        sa.Column("period_start", sa.DateTime, nullable=False),
        sa.Column("period_end", sa.DateTime, nullable=False),
        # Timestamps
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_usage_records_subscription_id", "usage_records", ["subscription_id"])
    op.create_index("ix_usage_records_usage_type", "usage_records", ["usage_type"])
    op.create_index("ix_usage_records_period_start", "usage_records", ["period_start"])

    # Insert default plans
    op.execute(
        """
        INSERT INTO subscription_plans (
            id, tier, name, description, price_monthly,
            chat_sessions_per_month, void_analyses_per_month, demographics_reports_per_month,
            emails_per_month, documents_per_month, team_members,
            has_placer_access, has_siteusa_access, has_costar_access,
            has_email_outreach, has_api_access
        ) VALUES
        (
            'plan_free_001', 'free', 'Free', 'Get started with SpaceFit', 0,
            10, 3, 5, 0, 5, 1,
            false, false, false, false, false
        ),
        (
            'plan_pro_001', 'pro', 'Pro', 'For growing CRE professionals', 4900,
            -1, 50, -1, 500, 50, 3,
            true, true, false, true, false
        ),
        (
            'plan_ent_001', 'enterprise', 'Enterprise', 'For teams that need everything', 19900,
            -1, -1, -1, 5000, -1, -1,
            true, true, true, true, true
        )
        """
    )


def downgrade():
    op.drop_index("ix_usage_records_period_start", "usage_records")
    op.drop_index("ix_usage_records_usage_type", "usage_records")
    op.drop_index("ix_usage_records_subscription_id", "usage_records")
    op.drop_table("usage_records")

    op.drop_index("ix_subscriptions_stripe_subscription_id", "subscriptions")
    op.drop_index("ix_subscriptions_stripe_customer_id", "subscriptions")
    op.drop_index("ix_subscriptions_plan_id", "subscriptions")
    op.drop_index("ix_subscriptions_user_id", "subscriptions")
    op.drop_table("subscriptions")

    op.drop_index("ix_subscription_plans_tier", "subscription_plans")
    op.drop_table("subscription_plans")
