"""add tool_call_log

Revision ID: 025
Revises: 024
Create Date: 2026-04-19

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "025"
down_revision = "024"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tool_call_log",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "session_id",
            sa.String(36),
            sa.ForeignKey("chat_sessions.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("tool_name", sa.String(100), nullable=False),
        sa.Column("arguments_json", sa.Text, nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("elapsed_ms", sa.Integer, nullable=False),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column(
            "created_at", sa.DateTime, nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("ix_tool_call_log_user_id", "tool_call_log", ["user_id"])
    op.create_index("ix_tool_call_log_session_id", "tool_call_log", ["session_id"])
    op.create_index("ix_tool_call_log_tool_name", "tool_call_log", ["tool_name"])
    op.create_index("ix_tool_call_log_created_at", "tool_call_log", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_tool_call_log_created_at", table_name="tool_call_log")
    op.drop_index("ix_tool_call_log_tool_name", table_name="tool_call_log")
    op.drop_index("ix_tool_call_log_session_id", table_name="tool_call_log")
    op.drop_index("ix_tool_call_log_user_id", table_name="tool_call_log")
    op.drop_table("tool_call_log")
