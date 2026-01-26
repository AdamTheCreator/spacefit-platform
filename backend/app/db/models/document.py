"""
Document models for parsed flyers, brochures, and generated memos.
"""
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models.deal import Property
    from app.db.models.user import User


def utc_now() -> datetime:
    return datetime.utcnow()


def uuid_str() -> str:
    return str(uuid.uuid4())


class DocumentType(str, Enum):
    LEASING_FLYER = "leasing_flyer"
    SITE_PLAN = "site_plan"
    VOID_ANALYSIS = "void_analysis"
    INVESTMENT_MEMO = "investment_memo"
    LOAN_DOCUMENT = "loan_document"
    COMP_REPORT = "comp_report"
    OTHER = "other"


class DocumentStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class ParsedDocument(Base):
    """
    A document uploaded by a user for parsing.
    Could be a leasing flyer, void analysis, investment memo, etc.
    """
    __tablename__ = "parsed_documents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    property_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("properties.id", ondelete="SET NULL"), nullable=True
    )

    # File info
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)  # S3 or local path
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)  # bytes
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Classification
    document_type: Mapped[str] = mapped_column(String(50), default=DocumentType.OTHER.value)
    confidence_score: Mapped[float | None] = mapped_column(Float, nullable=True)  # 0-1

    # Parsing status
    status: Mapped[str] = mapped_column(String(20), default=DocumentStatus.PENDING.value)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Extracted data (JSON blob for flexibility)
    extracted_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Analysis session link (created when user starts analysis from this document)
    analysis_session_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("chat_sessions.id", ondelete="SET NULL"), nullable=True
    )

    # Relationships
    user: Mapped["User"] = relationship(back_populates="documents")
    property: Mapped["Property | None"] = relationship(back_populates="documents")
    available_spaces: Mapped[list["AvailableSpace"]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )
    existing_tenants: Mapped[list["ExistingTenant"]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )


class AvailableSpace(Base):
    """
    An available space extracted from a leasing flyer.
    Represents a specific suite/unit that's available for lease.
    """
    __tablename__ = "available_spaces"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    document_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("parsed_documents.id", ondelete="CASCADE"), nullable=False
    )
    property_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("properties.id", ondelete="SET NULL"), nullable=True
    )

    # Space details
    suite_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    building_address: Mapped[str | None] = mapped_column(String(255), nullable=True)
    square_footage: Mapped[int | None] = mapped_column(Integer, nullable=True)
    min_divisible_sf: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_contiguous_sf: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Pricing
    asking_rent_psf: Mapped[float | None] = mapped_column(Float, nullable=True)
    rent_type: Mapped[str | None] = mapped_column(String(20), nullable=True)  # NNN, Gross, Modified Gross

    # Status
    is_endcap: Mapped[bool] = mapped_column(Boolean, default=False)
    is_anchor: Mapped[bool] = mapped_column(Boolean, default=False)
    has_drive_thru: Mapped[bool] = mapped_column(Boolean, default=False)
    has_patio: Mapped[bool] = mapped_column(Boolean, default=False)

    # Additional features (JSON for flexibility)
    features: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Previous tenant (if known)
    previous_tenant: Mapped[str | None] = mapped_column(String(255), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)

    # Relationships
    document: Mapped["ParsedDocument"] = relationship(back_populates="available_spaces")
    property: Mapped["Property | None"] = relationship()


class ExistingTenant(Base):
    """
    A current tenant at a property, extracted from a leasing flyer.
    """
    __tablename__ = "existing_tenants"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    document_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("parsed_documents.id", ondelete="CASCADE"), nullable=False
    )
    property_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("properties.id", ondelete="SET NULL"), nullable=True
    )

    # Tenant info
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str | None] = mapped_column(String(100), nullable=True)  # dining, retail, service, etc.
    suite_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    square_footage: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Classification flags
    is_anchor: Mapped[bool] = mapped_column(Boolean, default=False)
    is_national: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)

    # Relationships
    document: Mapped["ParsedDocument"] = relationship(back_populates="existing_tenants")
    property: Mapped["Property | None"] = relationship()


class VoidAnalysisResult(Base):
    """
    Stores void analysis results - gaps in tenant categories for a property.
    Can be generated from uploaded void analysis PDFs or computed by our agents.
    """
    __tablename__ = "void_analysis_results"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    document_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("parsed_documents.id", ondelete="SET NULL"), nullable=True
    )
    property_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("properties.id", ondelete="SET NULL"), nullable=True
    )
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )

    # Analysis parameters
    radius_miles: Mapped[float | None] = mapped_column(Float, nullable=True)
    analysis_date: Mapped[datetime] = mapped_column(DateTime, default=utc_now)

    # Results stored as JSON for flexibility
    # Structure: { category: { voids: [...], existing: [...], score: float } }
    results: Mapped[dict] = mapped_column(JSON, nullable=False)

    # Summary metrics
    total_voids: Mapped[int] = mapped_column(Integer, default=0)
    high_priority_voids: Mapped[int] = mapped_column(Integer, default=0)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


class InvestmentMemo(Base):
    """
    Generated investment memo/one-pager for a property.
    Combines data from multiple agents into a formatted document.
    """
    __tablename__ = "investment_memos"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    property_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("properties.id", ondelete="SET NULL"), nullable=True
    )

    # Memo info
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1)

    # Content sections (JSON for flexibility)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    location_highlights: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    financials: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    demographics: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    tenant_interest: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    scope_of_work: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Generated file
    pdf_path: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Status
    is_draft: Mapped[bool] = mapped_column(Boolean, default=True)
    shared_with: Mapped[list | None] = mapped_column(JSON, nullable=True)  # list of email addresses

    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now)
