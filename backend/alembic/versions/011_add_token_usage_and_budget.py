"""Add token_usage table and monthly_token_budget to subscription_plans

Revision ID: 011
Revises: 009
Create Date: 2026-03-04
"""

from alembic import op
import sqlalchemy as sa

revision = "011"
down_revision = "009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add monthly_token_budget column to subscription_plans
    op.add_column(
        "subscription_plans",
        sa.Column("monthly_token_budget", sa.Integer(), nullable=False, server_default="500000"),
    )

    # Create token_usage table
    op.create_table(
        "token_usage",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("period_start", sa.DateTime(), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("output_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("llm_calls", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_token_usage_user_period", "token_usage", ["user_id", "period_start"])


def downgrade() -> None:
    op.drop_index("ix_token_usage_user_period", table_name="token_usage")
    op.drop_table("token_usage")
    op.drop_column("subscription_plans", "monthly_token_budget")
