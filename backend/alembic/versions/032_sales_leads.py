"""sales lead capture table

Revision ID: 032
Revises: 031
Create Date: 2026-05-19

Adds a dedicated table to capture inbound enterprise inquiries from
the pricing page. Kept independent of the ``users`` table so prospects
can submit a lead without an account.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "032"
down_revision: str = "031"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "sales_leads",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("company_name", sa.String(length=255), nullable=True),
        sa.Column("team_size", sa.String(length=20), nullable=True),
        sa.Column("current_tools", sa.Text(), nullable=True),
        sa.Column("use_case", sa.Text(), nullable=True),
        sa.Column(
            "source",
            sa.String(length=50),
            server_default="pricing_page",
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.String(length=30),
            server_default="new",
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.String(length=36),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("contacted_at", sa.DateTime(), nullable=True),
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
    op.create_index("ix_sales_leads_created_at", "sales_leads", ["created_at"])
    op.create_index("ix_sales_leads_status", "sales_leads", ["status"])


def downgrade() -> None:
    op.drop_index("ix_sales_leads_status", table_name="sales_leads")
    op.drop_index("ix_sales_leads_created_at", table_name="sales_leads")
    op.drop_table("sales_leads")
