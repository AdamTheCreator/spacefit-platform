"""Add connector health fields to site_credentials

Adds columns for the connector health state machine:
- connector_status: current state (connected/stale/needs_reauth/degraded/error/disabled)
- health_meta: JSON blob for circuit breaker, probe history, rate limits
- last_probe_at: when the last health probe ran
- disabled_at: when the user disabled the connector
- disabled_reason: why the connector was disabled

Revision ID: 009
Revises: 008
Create Date: 2026-01-27
"""

from alembic import op
import sqlalchemy as sa

revision = "009"
down_revision = "008"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "site_credentials",
        sa.Column("connector_status", sa.String(20), server_default="stale"),
    )
    op.add_column(
        "site_credentials",
        sa.Column("health_meta", sa.Text, nullable=True),
    )
    op.add_column(
        "site_credentials",
        sa.Column("last_probe_at", sa.DateTime, nullable=True),
    )
    op.add_column(
        "site_credentials",
        sa.Column("disabled_at", sa.DateTime, nullable=True),
    )
    op.add_column(
        "site_credentials",
        sa.Column("disabled_reason", sa.Text, nullable=True),
    )

    # Back-fill: credentials with session_status='valid' → 'connected', others → 'stale'
    op.execute(
        "UPDATE site_credentials SET connector_status = 'connected' "
        "WHERE session_status = 'valid'"
    )
    op.execute(
        "UPDATE site_credentials SET connector_status = 'stale' "
        "WHERE connector_status IS NULL OR connector_status = 'stale'"
    )


def downgrade():
    op.drop_column("site_credentials", "disabled_reason")
    op.drop_column("site_credentials", "disabled_at")
    op.drop_column("site_credentials", "last_probe_at")
    op.drop_column("site_credentials", "health_meta")
    op.drop_column("site_credentials", "connector_status")
