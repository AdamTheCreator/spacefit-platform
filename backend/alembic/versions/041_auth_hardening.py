"""auth hardening: audit log + refresh-token lineage + password_changed_at

Revision ID: 041
Revises: 040

Additive, forward-only. Adds:
- ``auth_events`` append-only audit table (login, failed login, reset
  requested/completed, password changed, email verified, lockout, refresh
  reuse). Never stores passwords/tokens/links.
- ``refresh_tokens.family_id`` + ``refresh_tokens.replaced_by_id`` for
  refresh-reuse detection (a null family is treated as its own family).
- ``users.password_changed_at`` for audit + "sign out everywhere".
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "041"
down_revision: str = "040"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "auth_events",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=True),
        sa.Column("event", sa.String(length=40), nullable=False),
        sa.Column("ip_address", sa.String(length=64), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("request_id", sa.String(length=64), nullable=True),
        sa.Column("detail", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_auth_events_user_id", "auth_events", ["user_id"])
    op.create_index("ix_auth_events_event", "auth_events", ["event"])
    op.create_index("ix_auth_events_created_at", "auth_events", ["created_at"])

    op.add_column(
        "refresh_tokens",
        sa.Column("family_id", sa.String(length=36), nullable=True),
    )
    op.add_column(
        "refresh_tokens",
        sa.Column("replaced_by_id", sa.String(length=36), nullable=True),
    )

    op.add_column(
        "users",
        sa.Column("password_changed_at", sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("users", "password_changed_at")
    op.drop_column("refresh_tokens", "replaced_by_id")
    op.drop_column("refresh_tokens", "family_id")
    op.drop_index("ix_auth_events_created_at", table_name="auth_events")
    op.drop_index("ix_auth_events_event", table_name="auth_events")
    op.drop_index("ix_auth_events_user_id", table_name="auth_events")
    op.drop_table("auth_events")
