"""outreach voice profiles: per-user prompts for in-voice email generation

Revision ID: 038
Revises: 037
Create Date: 2026-06-03

Backs the "write like me" feature: a user keeps one or more named voice
profiles whose ``instructions`` (+ optional ``sample`` / ``signature``) are
injected into the AI outreach-email generator so drafts read in their voice.
``user_id`` is denormalized for cheap auth + scope filtering. Defaults are
applied Python-side by the ORM model (brand-new table, nothing to backfill),
so columns are created without server defaults.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "038"
down_revision: str = "037"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "outreach_voice_profiles",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "user_id",
            sa.String(length=36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("instructions", sa.Text(), nullable=False),
        sa.Column("tone", sa.String(length=255), nullable=True),
        sa.Column("sample", sa.Text(), nullable=True),
        sa.Column("signature", sa.Text(), nullable=True),
        sa.Column("is_default", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index(
        "ix_outreach_voice_profiles_user_id",
        "outreach_voice_profiles",
        ["user_id"],
    )


def downgrade() -> None:
    op.drop_table("outreach_voice_profiles")
