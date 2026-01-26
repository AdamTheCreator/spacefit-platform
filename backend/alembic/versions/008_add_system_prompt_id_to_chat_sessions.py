"""Add system_prompt_id to chat_sessions

Adds system_prompt_id column to chat_sessions so each conversation
can reference a specific system prompt from the Prompt Registry.
Existing sessions default to MASTER_DEFAULT; void analysis sessions
are back-filled to VOID_ANALYSIS.

Revision ID: 008
Revises: 007
Create Date: 2026-01-26
"""

from alembic import op
import sqlalchemy as sa

revision = "008"
down_revision = "007"
branch_labels = None
depends_on = None


def upgrade():
    # Add the column with a server default so existing rows get a value
    op.add_column(
        "chat_sessions",
        sa.Column(
            "system_prompt_id",
            sa.String(50),
            nullable=True,
            server_default="MASTER_DEFAULT",
        ),
    )

    # Back-fill existing void analysis sessions
    op.execute(
        "UPDATE chat_sessions SET system_prompt_id = 'VOID_ANALYSIS' "
        "WHERE analysis_type = 'void_analysis'"
    )

    # Back-fill remaining sessions that still have NULL
    op.execute(
        "UPDATE chat_sessions SET system_prompt_id = 'MASTER_DEFAULT' "
        "WHERE system_prompt_id IS NULL"
    )


def downgrade():
    op.drop_column("chat_sessions", "system_prompt_id")
