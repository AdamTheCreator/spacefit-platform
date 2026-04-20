"""add import_jobs table

Revision ID: 024
Revises: 023
Create Date: 2026-04-19

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "024"
down_revision: str = "023"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "import_jobs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "project_id",
            sa.String(36),
            sa.ForeignKey("projects.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("source", sa.String(32), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="parsing"),
        sa.Column("original_filename", sa.String(500), nullable=False),
        sa.Column("parsed_payload_json", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("record_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_import_jobs_user_id", "import_jobs", ["user_id"])
    op.create_index("ix_import_jobs_project_id", "import_jobs", ["project_id"])
    op.create_index("ix_import_jobs_created_at", "import_jobs", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_import_jobs_created_at", table_name="import_jobs")
    op.drop_index("ix_import_jobs_project_id", table_name="import_jobs")
    op.drop_index("ix_import_jobs_user_id", table_name="import_jobs")
    op.drop_table("import_jobs")
