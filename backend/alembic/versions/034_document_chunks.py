"""document_chunks table for project document Q&A

Revision ID: 034
Revises: 033
Create Date: 2026-05-19

Splits each parsed document into ~800-token chunks with a Postgres
``tsvector`` index so the chat can answer "what does the OM say about
the loan covenant?" via a ``document_search`` MCP tool.

The ``embedding`` column is a deliberate ``BYTEA`` placeholder so we
can swap it for ``pgvector(N)`` later without altering the rest of the
row shape. ``user_id`` and ``project_id`` are denormalized onto the
chunk row so the auth + scope filter is a cheap b-tree lookup instead
of two joins.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "034"
down_revision: str = "033"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "document_chunks",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "document_id",
            sa.String(length=36),
            sa.ForeignKey("parsed_documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.String(length=36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "project_id",
            sa.String(length=36),
            sa.ForeignKey("projects.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=True),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("token_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("embedding", sa.LargeBinary(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    # Generated tsvector column for full-text search.
    op.execute(
        "ALTER TABLE document_chunks "
        "ADD COLUMN search_vector tsvector "
        "GENERATED ALWAYS AS (to_tsvector('english', coalesce(text, ''))) STORED"
    )

    op.create_index(
        "idx_doc_chunks_search",
        "document_chunks",
        ["search_vector"],
        postgresql_using="gin",
    )
    op.create_index(
        "idx_doc_chunks_project", "document_chunks", ["project_id"]
    )
    op.create_index(
        "idx_doc_chunks_document", "document_chunks", ["document_id"]
    )
    op.create_index(
        "idx_doc_chunks_user_project",
        "document_chunks",
        ["user_id", "project_id"],
    )


def downgrade() -> None:
    op.drop_index("idx_doc_chunks_user_project", table_name="document_chunks")
    op.drop_index("idx_doc_chunks_document", table_name="document_chunks")
    op.drop_index("idx_doc_chunks_project", table_name="document_chunks")
    op.drop_index("idx_doc_chunks_search", table_name="document_chunks")
    op.drop_table("document_chunks")
