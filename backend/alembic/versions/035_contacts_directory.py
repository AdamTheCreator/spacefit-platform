"""contacts directory: companies, contacts, contact_interactions

Revision ID: 035
Revises: 034
Create Date: 2026-06-03

Real per-user contacts directory replacing the hardcoded frontend mock.
Companies carry the explicit tenant/expansion criteria the directory shows
(sector, SF range, target markets, expanding flag) plus a flexible ``criteria``
JSON "buy box" for the future client-fit Search engine. ``user_id`` is
denormalized onto every row for cheap auth + scope filtering.

Defaults are applied Python-side by the ORM models (these are brand-new tables
with no existing rows to backfill), so the columns are created without server
defaults.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "035"
down_revision: str = "034"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "companies",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "user_id",
            sa.String(length=36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("sector", sa.String(length=100), nullable=True),
        sa.Column("subsector", sa.String(length=100), nullable=True),
        sa.Column("us_locations", sa.Integer(), nullable=True),
        sa.Column("is_expanding", sa.Boolean(), nullable=True),
        sa.Column("target_markets", sa.JSON(), nullable=True),
        sa.Column("sf_min", sa.Integer(), nullable=True),
        sa.Column("sf_max", sa.Integer(), nullable=True),
        sa.Column("website", sa.String(length=255), nullable=True),
        sa.Column("criteria", sa.JSON(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("enriched_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_companies_user_id", "companies", ["user_id"])

    op.create_table(
        "contacts",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "company_id",
            sa.String(length=36),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.String(length=36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("first", sa.String(length=100), nullable=False),
        sa.Column("last", sa.String(length=100), nullable=True),
        sa.Column("role", sa.String(length=150), nullable=True),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("phone", sa.String(length=50), nullable=True),
        sa.Column("verif", sa.String(length=20), nullable=False),
        sa.Column("source", sa.String(length=30), nullable=False),
        sa.Column("linkedin", sa.Boolean(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("last_verified_at", sa.DateTime(), nullable=True),
        sa.Column("last_contacted_at", sa.DateTime(), nullable=True),
        sa.Column("last_reply_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_contacts_user_id", "contacts", ["user_id"])
    op.create_index("ix_contacts_company_id", "contacts", ["company_id"])

    op.create_table(
        "contact_interactions",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "contact_id",
            sa.String(length=36),
            sa.ForeignKey("contacts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.String(length=36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("type", sa.String(length=20), nullable=False),
        sa.Column("occurred_at", sa.DateTime(), nullable=False),
        sa.Column("who", sa.String(length=150), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=True),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index(
        "ix_contact_interactions_contact_id",
        "contact_interactions",
        ["contact_id"],
    )
    op.create_index(
        "ix_contact_interactions_user_id",
        "contact_interactions",
        ["user_id"],
    )


def downgrade() -> None:
    op.drop_table("contact_interactions")
    op.drop_table("contacts")
    op.drop_table("companies")
