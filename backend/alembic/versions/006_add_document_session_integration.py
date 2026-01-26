"""Add document-to-session integration fields

Adds fields to support automatic void analysis session creation from parsed documents:
- analysis_session_id on parsed_documents (link to created chat session)
- source_document_id on chat_sessions (link to source document)
- document_context on chat_sessions (JSON blob with extracted property data)

Revision ID: 006
Revises: 005
Create Date: 2026-01-25
"""

from alembic import op
import sqlalchemy as sa

revision = "006"
down_revision = "005"
branch_labels = None
depends_on = None


def upgrade():
    # Add analysis_session_id to parsed_documents
    # Links document to the chat session created for analysis
    # Note: SQLite doesn't support ALTER with FK constraints, so we add plain column
    # FK relationship is enforced at application level via SQLAlchemy
    op.add_column(
        "parsed_documents",
        sa.Column("analysis_session_id", sa.String(36), nullable=True),
    )

    # Add source_document_id to chat_sessions
    # Links chat session back to the source document
    op.add_column(
        "chat_sessions",
        sa.Column("source_document_id", sa.String(36), nullable=True),
    )

    # Add document_context to chat_sessions
    # Stores extracted property data (address, tenants, spaces) for analysis
    op.add_column(
        "chat_sessions",
        sa.Column("document_context", sa.JSON, nullable=True),
    )

    # Create indexes for efficient lookups
    op.create_index(
        "ix_parsed_documents_analysis_session_id",
        "parsed_documents",
        ["analysis_session_id"],
    )
    op.create_index(
        "ix_chat_sessions_source_document_id",
        "chat_sessions",
        ["source_document_id"],
    )


def downgrade():
    # Drop indexes first
    op.drop_index("ix_chat_sessions_source_document_id", "chat_sessions")
    op.drop_index("ix_parsed_documents_analysis_session_id", "parsed_documents")

    # Drop columns
    op.drop_column("chat_sessions", "document_context")
    op.drop_column("chat_sessions", "source_document_id")
    op.drop_column("parsed_documents", "analysis_session_id")
