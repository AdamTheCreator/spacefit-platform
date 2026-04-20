"""add user_memory table

Revision ID: 014
Revises: 013
Create Date: 2026-03-08
"""
from alembic import op
import sqlalchemy as sa

revision = '014'
down_revision = '013'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'user_memory',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, unique=True),
        sa.Column('analyzed_properties', sa.JSON, nullable=False, server_default='[]'),
        sa.Column('book_of_business_summary', sa.JSON, nullable=False, server_default='{}'),
        sa.Column('preferences', sa.JSON, nullable=False, server_default='{}'),
        sa.Column('ai_profile_summary', sa.Text, nullable=True),
        sa.Column('total_analyses', sa.Integer, nullable=False, server_default='0'),
        sa.Column('last_updated', sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
    )
    op.create_index('ix_user_memory_user_id', 'user_memory', ['user_id'])


def downgrade() -> None:
    op.drop_index('ix_user_memory_user_id')
    op.drop_table('user_memory')
