"""Add browser session tracking columns to site_credentials

Revision ID: 003_add_browser_session_tracking
Revises: 002_add_deals_and_documents
Create Date: 2025-01-11
"""

from alembic import op
import sqlalchemy as sa

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade():
    # Add session tracking columns to site_credentials
    op.add_column(
        "site_credentials",
        sa.Column("session_status", sa.String(20), server_default="unknown"),
    )
    op.add_column(
        "site_credentials",
        sa.Column("session_last_checked", sa.DateTime, nullable=True),
    )
    op.add_column(
        "site_credentials",
        sa.Column("session_error_message", sa.Text, nullable=True),
    )

    # Add usage tracking columns
    op.add_column(
        "site_credentials",
        sa.Column("last_used_at", sa.DateTime, nullable=True),
    )
    op.add_column(
        "site_credentials",
        sa.Column("total_uses", sa.Integer, server_default="0"),
    )


def downgrade():
    op.drop_column("site_credentials", "total_uses")
    op.drop_column("site_credentials", "last_used_at")
    op.drop_column("site_credentials", "session_error_message")
    op.drop_column("site_credentials", "session_last_checked")
    op.drop_column("site_credentials", "session_status")
