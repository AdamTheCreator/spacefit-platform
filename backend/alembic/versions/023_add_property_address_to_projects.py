"""add property_address to projects

Revision ID: 023
Revises: 022
Create Date: 2026-04-01

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "023"
down_revision: str = "022"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_exists(table: str, column: str) -> bool:
    conn = op.get_bind()
    insp = sa.inspect(conn)
    return any(c["name"] == column for c in insp.get_columns(table))


def upgrade() -> None:
    if not _column_exists("projects", "property_address"):
        op.add_column(
            "projects",
            sa.Column("property_address", sa.String(500), nullable=True),
        )


def downgrade() -> None:
    if _column_exists("projects", "property_address"):
        op.drop_column("projects", "property_address")
