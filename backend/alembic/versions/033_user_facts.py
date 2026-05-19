"""user_facts table for memory + personalization

Revision ID: 033
Revises: 032
Create Date: 2026-05-19

Captures durable, free-form facts about a user that the AI has
inferred from chat. Facts are extracted post-message into ``pending``
status and surfaced in a sidebar; the user approves or rejects each
one before it gets injected into future system prompts.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "033"
down_revision: str = "032"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "user_facts",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "user_id",
            sa.String(length=36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column(
            "category",
            sa.String(length=40),
            server_default="other",
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.String(length=20),
            server_default="pending",
            nullable=False,
        ),
        sa.Column("confidence", sa.Float(), server_default="0.5", nullable=False),
        sa.Column(
            "source_session_id",
            sa.String(length=36),
            sa.ForeignKey("chat_sessions.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "source_message_id",
            sa.String(length=36),
            sa.ForeignKey("chat_messages.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("approved_at", sa.DateTime(), nullable=True),
        sa.Column("last_used_at", sa.DateTime(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_user_facts_user_status", "user_facts", ["user_id", "status"]
    )
    op.create_index(
        "ix_user_facts_user_last_used",
        "user_facts",
        ["user_id", "last_used_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_user_facts_user_last_used", table_name="user_facts")
    op.drop_index("ix_user_facts_user_status", table_name="user_facts")
    op.drop_table("user_facts")
