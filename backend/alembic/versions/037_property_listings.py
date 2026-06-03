"""property listings: client-fit matching engine source data

Revision ID: 037
Revises: 036
Create Date: 2026-06-03

Imported CRE for-sale listings, scored against a ``Company``'s buy-box by the
client-fit matching engine (the inverse of the void/matchmaker flow).
``asset_type`` and ``source`` are plain VARCHAR (no native PG enum) and are
validated Pydantic-side. ``user_id`` is denormalized for cheap auth + scope
filtering.

Defaults are applied Python-side by the ORM model (a brand-new table with no
rows to backfill), so the columns are created without server defaults.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "037"
down_revision: str = "036"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "property_listings",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "user_id",
            sa.String(length=36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("address", sa.String(length=500), nullable=True),
        sa.Column("city", sa.String(length=255), nullable=True),
        sa.Column("state", sa.String(length=255), nullable=True),
        sa.Column("zip_code", sa.String(length=20), nullable=True),
        sa.Column("asset_type", sa.String(length=50), nullable=True),
        sa.Column("size_sf", sa.Integer(), nullable=True),
        sa.Column("price", sa.BigInteger(), nullable=True),
        sa.Column("cap_rate", sa.Float(), nullable=True),
        sa.Column("year_built", sa.Integer(), nullable=True),
        sa.Column("units", sa.Integer(), nullable=True),
        sa.Column("listing_url", sa.String(length=500), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("source", sa.String(length=50), nullable=False),
        sa.Column("raw", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index(
        "ix_property_listings_user_id", "property_listings", ["user_id"]
    )


def downgrade() -> None:
    op.drop_table("property_listings")
