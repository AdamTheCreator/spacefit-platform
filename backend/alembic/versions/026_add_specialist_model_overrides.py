"""add specialist_models_json to user_ai_configs

Revision ID: 026
Revises: 025
Create Date: 2026-04-19

"""
from alembic import op
import sqlalchemy as sa


revision = "026"
down_revision = "025"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "user_ai_configs",
        sa.Column("specialist_models_json", sa.Text, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("user_ai_configs", "specialist_models_json")
