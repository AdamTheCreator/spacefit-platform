"""add archive flags to projects and parsed documents

Revision ID: 022
Revises: 021
Create Date: 2026-03-17

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "022"
down_revision: str = "021"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_exists(table: str, column: str) -> bool:
    conn = op.get_bind()
    result = conn.execute(sa.text(f"PRAGMA table_info({table})"))
    return any(row[1] == column for row in result.fetchall())


def upgrade() -> None:
    if not _column_exists("projects", "is_archived"):
      op.add_column(
          "projects",
          sa.Column("is_archived", sa.Boolean(), nullable=False, server_default=sa.false()),
      )

    if not _column_exists("parsed_documents", "is_archived"):
      op.add_column(
          "parsed_documents",
          sa.Column("is_archived", sa.Boolean(), nullable=False, server_default=sa.false()),
      )


def downgrade() -> None:
    if _column_exists("parsed_documents", "is_archived"):
        op.drop_column("parsed_documents", "is_archived")

    if _column_exists("projects", "is_archived"):
        op.drop_column("projects", "is_archived")
