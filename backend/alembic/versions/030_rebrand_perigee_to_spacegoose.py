"""rebrand: update legacy Perigee/SpaceFit copy in seeded rows to Space Goose

Revision ID: 030
Revises: 029
Create Date: 2026-04-23

Product was seeded in 005 with 'Get started with SpaceFit' and later
re-seeded in code (app/services/subscription.py) as 'Get started with
Perigee'. After the spacegoose.ai rebrand the code constant is now
'Get started with Space Goose'; this migration brings existing
deployments' rows in line so the UI doesn't show stale brand text.

Any future brand-owned literal rows that drift should be added here
rather than via ad-hoc SQL so deployments stay reproducible.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "030"
down_revision: str = "029"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


NEW_FREE_DESCRIPTION = "Get started with Space Goose"


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        sa.text(
            """
            UPDATE subscription_plans
            SET description = :new_description
            WHERE description IN (
                'Get started with SpaceFit',
                'Get started with Perigee'
            )
            """
        ),
        {"new_description": NEW_FREE_DESCRIPTION},
    )


def downgrade() -> None:
    # No-op: the brand rename is not reversed. The prior text was itself a
    # historical brand ('SpaceFit' -> 'Perigee' -> 'Space Goose'), and
    # downgrading would have to pick one arbitrarily. Leave rows as-is.
    pass
