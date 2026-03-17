"""add projects table and FK columns

Revision ID: 020
Revises: 019
Create Date: 2026-03-16

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '020'
down_revision: str = '019'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(name: str) -> bool:
    conn = op.get_bind()
    result = conn.execute(
        sa.text("SELECT name FROM sqlite_master WHERE type='table' AND name=:n"),
        {"n": name},
    )
    return result.fetchone() is not None


def _column_exists(table: str, column: str) -> bool:
    conn = op.get_bind()
    result = conn.execute(sa.text(f"PRAGMA table_info({table})"))
    return any(row[1] == column for row in result.fetchall())


def upgrade() -> None:
    # Create projects table (idempotent)
    if not _table_exists('projects'):
        op.create_table(
            'projects',
            sa.Column('id', sa.String(36), primary_key=True),
            sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
            sa.Column('property_id', sa.String(36), sa.ForeignKey('properties.id', ondelete='SET NULL'), nullable=True),
            sa.Column('name', sa.String(255), nullable=False),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('instructions', sa.Text(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), nullable=False),
        )
        op.create_index('ix_projects_user_id', 'projects', ['user_id'])

    # Add project_id to parsed_documents (without FK constraint for SQLite compat)
    if not _column_exists('parsed_documents', 'project_id'):
        op.add_column(
            'parsed_documents',
            sa.Column('project_id', sa.String(36), nullable=True),
        )
        op.create_index('ix_parsed_documents_project_id', 'parsed_documents', ['project_id'])

    # Add project_id to chat_sessions (without FK constraint for SQLite compat)
    if not _column_exists('chat_sessions', 'project_id'):
        op.add_column(
            'chat_sessions',
            sa.Column('project_id', sa.String(36), nullable=True),
        )
        op.create_index('ix_chat_sessions_project_id', 'chat_sessions', ['project_id'])


def downgrade() -> None:
    op.drop_index('ix_chat_sessions_project_id', table_name='chat_sessions')
    op.drop_column('chat_sessions', 'project_id')

    op.drop_index('ix_parsed_documents_project_id', table_name='parsed_documents')
    op.drop_column('parsed_documents', 'project_id')

    op.drop_index('ix_projects_user_id', table_name='projects')
    op.drop_table('projects')
