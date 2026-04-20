"""rebrand free-plan description to Perigee

Migration 005 seeded the free plan with description 'Get started with SpaceFit'.
After the Spacefit -> Perigee rebrand, this row needs to be updated in any
database that ran migration 005 before rebrand. The Python code that writes
this description (backend/app/services/subscription.py) was updated in a
previous commit to use 'Perigee' going forward, so this migration fixes
historical data.

Revision ID: 027
Revises: 026
Create Date: 2026-04-20

"""
from alembic import op


revision = "027"
down_revision = "026"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "UPDATE subscription_plans "
        "SET description = 'Get started with Perigee' "
        "WHERE id = 'plan_free_001' "
        "  AND description = 'Get started with SpaceFit'"
    )


def downgrade() -> None:
    op.execute(
        "UPDATE subscription_plans "
        "SET description = 'Get started with SpaceFit' "
        "WHERE id = 'plan_free_001' "
        "  AND description = 'Get started with Perigee'"
    )
