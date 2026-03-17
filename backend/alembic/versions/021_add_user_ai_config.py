"""add user_ai_configs table for BYOK

Revision ID: 021
Revises: 020
Create Date: 2026-03-16

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '021'
down_revision: str = '020'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(name: str) -> bool:
    conn = op.get_bind()
    result = conn.execute(
        sa.text("SELECT name FROM sqlite_master WHERE type='table' AND name=:n"),
        {"n": name},
    )
    return result.fetchone() is not None


def upgrade() -> None:
    if _table_exists("user_ai_configs"):
        return

    op.create_table(
        "user_ai_configs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("provider", sa.String(30), server_default="platform_default", nullable=False),
        sa.Column("model", sa.String(100), nullable=True),
        sa.Column("api_key_encrypted", sa.LargeBinary, nullable=True),
        sa.Column("encryption_salt", sa.LargeBinary, nullable=True),
        sa.Column("base_url", sa.Text, nullable=True),
        sa.Column("is_key_valid", sa.Boolean, server_default="0", nullable=False),
        sa.Column("key_validated_at", sa.DateTime, nullable=True),
        sa.Column("key_error_message", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("updated_at", sa.DateTime, nullable=False),
    )


def downgrade() -> None:
    op.drop_table("user_ai_configs")
