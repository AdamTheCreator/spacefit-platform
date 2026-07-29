"""Add outreach_campaigns.deal_id link to the pipeline.

Revision ID: 042
Revises: 041
Create Date: 2026-07-03

Links a campaign to the ``deals`` row created when the campaign is sent, so
starting an outreach sequence drops a card on the Kanban board. Plain nullable
FK (no enum). ``ON DELETE SET NULL`` so deleting a deal doesn't cascade into the
campaign; indexed for campaign->deal lookups.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "042"
down_revision: str = "041"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "outreach_campaigns",
        sa.Column("deal_id", sa.String(length=36), nullable=True),
    )
    op.create_index(
        "ix_outreach_campaigns_deal_id", "outreach_campaigns", ["deal_id"]
    )
    op.create_foreign_key(
        "fk_outreach_campaigns_deal_id",
        "outreach_campaigns",
        "deals",
        ["deal_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_outreach_campaigns_deal_id", "outreach_campaigns", type_="foreignkey"
    )
    op.drop_index("ix_outreach_campaigns_deal_id", table_name="outreach_campaigns")
    op.drop_column("outreach_campaigns", "deal_id")
