"""normalize existing user emails to trimmed-lowercase

Revision ID: 040
Revises: 039

Signup and login now normalize email via ``app.models.user.normalize_email``
(trim + lowercase). Existing rows may have been stored with mixed casing or
surrounding whitespace, which would no longer match a normalized login lookup.
This migration canonicalizes ``users.email`` in place.

Collision-safe: if two rows collapse to the same normalized email, the
migration aborts and lists the offenders rather than blowing the unique
constraint, so a human can merge them deliberately. Downgrade is a no-op —
the original casing is not recoverable.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "040"
down_revision: str = "039"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()

    duplicates = conn.execute(
        sa.text(
            "SELECT lower(trim(email)) AS normalized, count(*) AS n "
            "FROM users GROUP BY lower(trim(email)) HAVING count(*) > 1"
        )
    ).fetchall()

    if duplicates:
        collisions = ", ".join(f"{row.normalized} (x{row.n})" for row in duplicates)
        raise RuntimeError(
            "Cannot normalize user emails: case/whitespace-variant duplicates "
            f"exist and must be merged first: {collisions}"
        )

    conn.execute(
        sa.text(
            "UPDATE users SET email = lower(trim(email)) "
            "WHERE email <> lower(trim(email))"
        )
    )


def downgrade() -> None:
    # Original casing is not recoverable; nothing to do.
    pass
