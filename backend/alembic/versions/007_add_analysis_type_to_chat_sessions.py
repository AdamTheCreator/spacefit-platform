"""Add analysis_type to chat_sessions

Adds analysis_type column to chat_sessions to track the type of analysis
(void_analysis, competitive_analysis, demographic_profile) for
document-linked sessions.

Revision ID: 007
Revises: 006
Create Date: 2026-01-26
"""

from alembic import op
import sqlalchemy as sa

revision = "007"
down_revision = "006"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "chat_sessions",
        sa.Column("analysis_type", sa.String(50), nullable=True),
    )


def downgrade():
    op.drop_column("chat_sessions", "analysis_type")
