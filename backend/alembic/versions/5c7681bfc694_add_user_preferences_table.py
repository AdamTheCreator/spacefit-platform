"""add user preferences table

Revision ID: 5c7681bfc694
Revises: 003
Create Date: 2026-01-12 16:36:41.464731

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5c7681bfc694'
down_revision: Union[str, None] = '003'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create user_preferences table
    op.create_table('user_preferences',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('user_id', sa.String(length=36), nullable=False),
        sa.Column('role', sa.String(length=50), nullable=True),
        sa.Column('property_types', sa.Text(), nullable=True),
        sa.Column('tenant_categories', sa.Text(), nullable=True),
        sa.Column('markets', sa.Text(), nullable=True),
        sa.Column('deal_size_min', sa.Integer(), nullable=True),
        sa.Column('deal_size_max', sa.Integer(), nullable=True),
        sa.Column('key_tenants', sa.Text(), nullable=True),
        sa.Column('analysis_priorities', sa.Text(), nullable=True),
        sa.Column('custom_notes', sa.Text(), nullable=True),
        sa.Column('is_complete', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id')
    )


def downgrade() -> None:
    op.drop_table('user_preferences')
