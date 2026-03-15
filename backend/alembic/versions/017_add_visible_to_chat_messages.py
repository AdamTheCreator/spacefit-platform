"""add visible column to chat_messages

Revision ID: 017
Revises: 016
Create Date: 2026-03-15

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '017'
down_revision: str = '016'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'chat_messages',
        sa.Column('visible', sa.Boolean(), nullable=False, server_default=sa.text('true')),
    )


def downgrade() -> None:
    op.drop_column('chat_messages', 'visible')
