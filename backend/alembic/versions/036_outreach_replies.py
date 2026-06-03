"""outreach replies: reply detection columns on outreach_recipients

Revision ID: 036
Revises: 035
Create Date: 2026-06-03

Phase 3b reply-triage path. Stores the detected inbound reply for a
recipient so the dashboard can show real replied threads instead of a
``replied_count`` placeholder. Columns are populated by the Gmail-backed
``sync_replies_for_user`` service when an inbound message from the
recipient is found; ``status`` stays a plain VARCHAR string (the
``native_enum=False`` convention — no PG enum is introduced here).

These add nullable columns to the existing ``outreach_recipients`` table
(no backfill, so no server defaults).
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "036"
down_revision: str = "035"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "outreach_recipients",
        sa.Column("reply_snippet", sa.Text(), nullable=True),
    )
    op.add_column(
        "outreach_recipients",
        sa.Column("reply_received_at", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "outreach_recipients",
        sa.Column("reply_message_id", sa.String(length=200), nullable=True),
    )
    op.add_column(
        "outreach_recipients",
        sa.Column("reply_thread_id", sa.String(length=200), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("outreach_recipients", "reply_thread_id")
    op.drop_column("outreach_recipients", "reply_message_id")
    op.drop_column("outreach_recipients", "reply_received_at")
    op.drop_column("outreach_recipients", "reply_snippet")
