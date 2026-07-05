"""document freshness: add parsed_documents.indexed_at

Revision ID: 040
Revises: 039
Create Date: 2026-07-04

Adds a nullable ``indexed_at`` timestamp to ``parsed_documents`` so the
chunker/reindex path can stamp each document with the last successful
indexing time. Additive nullable column with a working downgrade —
hand-written to avoid the ``document_chunks.search_vector`` autogenerate
false-drift.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "040"
down_revision: str = "039"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "parsed_documents",
        sa.Column("indexed_at", sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("parsed_documents", "indexed_at")
