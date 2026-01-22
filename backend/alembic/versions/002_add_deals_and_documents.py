"""Add deals, properties, and document tables

Revision ID: 002
Revises: 001
Create Date: 2025-01-11

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Properties table
    op.create_table(
        "properties",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("address", sa.String(500), nullable=False),
        sa.Column("city", sa.String(100), nullable=False),
        sa.Column("state", sa.String(50), nullable=False),
        sa.Column("zip_code", sa.String(20), nullable=False),
        sa.Column("latitude", sa.Float(), nullable=True),
        sa.Column("longitude", sa.Float(), nullable=True),
        sa.Column("property_type", sa.String(50), default="retail"),
        sa.Column("total_sf", sa.Integer(), nullable=True),
        sa.Column("available_sf", sa.Integer(), nullable=True),
        sa.Column("landlord_id", sa.String(36), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("idx_properties_user_id", "properties", ["user_id"])

    # Deals table
    op.create_table(
        "deals",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("property_id", sa.String(36), sa.ForeignKey("properties.id", ondelete="SET NULL"), nullable=True),
        sa.Column("customer_id", sa.String(36), sa.ForeignKey("customers.id", ondelete="SET NULL"), nullable=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("stage", sa.String(20), default="lead"),
        sa.Column("deal_type", sa.String(20), default="lease"),
        sa.Column("asking_rent_psf", sa.Float(), nullable=True),
        sa.Column("negotiated_rent_psf", sa.Float(), nullable=True),
        sa.Column("square_footage", sa.Integer(), nullable=True),
        sa.Column("commission_rate", sa.Float(), nullable=True),
        sa.Column("commission_amount", sa.Float(), nullable=True),
        sa.Column("probability", sa.Integer(), default=50),
        sa.Column("expected_close_date", sa.Date(), nullable=True),
        sa.Column("actual_close_date", sa.Date(), nullable=True),
        sa.Column("lease_start_date", sa.Date(), nullable=True),
        sa.Column("lease_term_months", sa.Integer(), nullable=True),
        sa.Column("source", sa.String(100), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("is_archived", sa.Boolean(), default=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("idx_deals_user_id", "deals", ["user_id"])
    op.create_index("idx_deals_stage", "deals", ["stage"])

    # Deal stage history table
    op.create_table(
        "deal_stage_history",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("deal_id", sa.String(36), sa.ForeignKey("deals.id", ondelete="CASCADE"), nullable=False),
        sa.Column("from_stage", sa.String(20), nullable=True),
        sa.Column("to_stage", sa.String(20), nullable=False),
        sa.Column("changed_by", sa.String(36), nullable=False),
        sa.Column("changed_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("notes", sa.Text(), nullable=True),
    )
    op.create_index("idx_deal_stage_history_deal_id", "deal_stage_history", ["deal_id"])

    # Deal activities table
    op.create_table(
        "deal_activities",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("deal_id", sa.String(36), sa.ForeignKey("deals.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.String(36), nullable=False),
        sa.Column("activity_type", sa.String(20), default="note"),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("scheduled_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("idx_deal_activities_deal_id", "deal_activities", ["deal_id"])

    # Parsed documents table
    op.create_table(
        "parsed_documents",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("property_id", sa.String(36), sa.ForeignKey("properties.id", ondelete="SET NULL"), nullable=True),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("file_path", sa.String(500), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=False),
        sa.Column("mime_type", sa.String(100), nullable=False),
        sa.Column("page_count", sa.Integer(), nullable=True),
        sa.Column("document_type", sa.String(50), default="other"),
        sa.Column("confidence_score", sa.Float(), nullable=True),
        sa.Column("status", sa.String(20), default="pending"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("extracted_data", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("processed_at", sa.DateTime(), nullable=True),
    )
    op.create_index("idx_parsed_documents_user_id", "parsed_documents", ["user_id"])
    op.create_index("idx_parsed_documents_status", "parsed_documents", ["status"])

    # Available spaces table
    op.create_table(
        "available_spaces",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("document_id", sa.String(36), sa.ForeignKey("parsed_documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("property_id", sa.String(36), sa.ForeignKey("properties.id", ondelete="SET NULL"), nullable=True),
        sa.Column("suite_number", sa.String(50), nullable=True),
        sa.Column("building_address", sa.String(255), nullable=True),
        sa.Column("square_footage", sa.Integer(), nullable=True),
        sa.Column("min_divisible_sf", sa.Integer(), nullable=True),
        sa.Column("max_contiguous_sf", sa.Integer(), nullable=True),
        sa.Column("asking_rent_psf", sa.Float(), nullable=True),
        sa.Column("rent_type", sa.String(20), nullable=True),
        sa.Column("is_endcap", sa.Boolean(), default=False),
        sa.Column("is_anchor", sa.Boolean(), default=False),
        sa.Column("has_drive_thru", sa.Boolean(), default=False),
        sa.Column("has_patio", sa.Boolean(), default=False),
        sa.Column("features", sa.JSON(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("previous_tenant", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("idx_available_spaces_document_id", "available_spaces", ["document_id"])

    # Existing tenants table
    op.create_table(
        "existing_tenants",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("document_id", sa.String(36), sa.ForeignKey("parsed_documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("property_id", sa.String(36), sa.ForeignKey("properties.id", ondelete="SET NULL"), nullable=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("category", sa.String(100), nullable=True),
        sa.Column("suite_number", sa.String(50), nullable=True),
        sa.Column("square_footage", sa.Integer(), nullable=True),
        sa.Column("is_anchor", sa.Boolean(), default=False),
        sa.Column("is_national", sa.Boolean(), default=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("idx_existing_tenants_document_id", "existing_tenants", ["document_id"])

    # Void analysis results table
    op.create_table(
        "void_analysis_results",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("document_id", sa.String(36), sa.ForeignKey("parsed_documents.id", ondelete="SET NULL"), nullable=True),
        sa.Column("property_id", sa.String(36), sa.ForeignKey("properties.id", ondelete="SET NULL"), nullable=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("radius_miles", sa.Float(), nullable=True),
        sa.Column("analysis_date", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("results", sa.JSON(), nullable=False),
        sa.Column("total_voids", sa.Integer(), default=0),
        sa.Column("high_priority_voids", sa.Integer(), default=0),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("idx_void_analysis_user_id", "void_analysis_results", ["user_id"])

    # Investment memos table
    op.create_table(
        "investment_memos",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("property_id", sa.String(36), sa.ForeignKey("properties.id", ondelete="SET NULL"), nullable=True),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("version", sa.Integer(), default=1),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("location_highlights", sa.JSON(), nullable=True),
        sa.Column("financials", sa.JSON(), nullable=True),
        sa.Column("demographics", sa.JSON(), nullable=True),
        sa.Column("tenant_interest", sa.JSON(), nullable=True),
        sa.Column("scope_of_work", sa.Text(), nullable=True),
        sa.Column("pdf_path", sa.String(500), nullable=True),
        sa.Column("is_draft", sa.Boolean(), default=True),
        sa.Column("shared_with", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("idx_investment_memos_user_id", "investment_memos", ["user_id"])


def downgrade() -> None:
    op.drop_table("investment_memos")
    op.drop_table("void_analysis_results")
    op.drop_table("existing_tenants")
    op.drop_table("available_spaces")
    op.drop_table("parsed_documents")
    op.drop_table("deal_activities")
    op.drop_table("deal_stage_history")
    op.drop_table("deals")
    op.drop_table("properties")
