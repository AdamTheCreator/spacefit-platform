"""add attachment_ids column to outreach_campaigns

Revision ID: 016
Revises: 015_qualification_funnel
Create Date: 2026-03-13

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '016'
down_revision: str = '015_qualification_funnel'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'outreach_campaigns',
        sa.Column('attachment_ids', sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('outreach_campaigns', 'attachment_ids')
