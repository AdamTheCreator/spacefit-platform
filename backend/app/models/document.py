"""
Pydantic models for document parsing API.
"""
from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field


class DocumentType(str, Enum):
    LEASING_FLYER = "leasing_flyer"
    SITE_PLAN = "site_plan"
    VOID_ANALYSIS = "void_analysis"
    INVESTMENT_MEMO = "investment_memo"
    OFFERING_MEMORANDUM = "offering_memorandum"
    LOI = "loi"
    LOAN_DOCUMENT = "loan_document"
    COMP_REPORT = "comp_report"
    OTHER = "other"


class DocumentStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


# Available Space Models
class AvailableSpaceBase(BaseModel):
    suite_number: str | None = None
    building_address: str | None = None
    square_footage: int | None = None
    min_divisible_sf: int | None = None
    max_contiguous_sf: int | None = None
    asking_rent_psf: float | None = None
    rent_type: str | None = None
    is_endcap: bool = False
    is_anchor: bool = False
    has_drive_thru: bool = False
    has_patio: bool = False
    features: dict | None = None
    notes: str | None = None
    previous_tenant: str | None = None


class AvailableSpaceResponse(AvailableSpaceBase):
    id: UUID
    document_id: UUID
    property_id: UUID | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


# Existing Tenant Models
class ExistingTenantBase(BaseModel):
    name: str
    category: str | None = None
    suite_number: str | None = None
    square_footage: int | None = None
    is_anchor: bool = False
    is_national: bool = False


class ExistingTenantResponse(ExistingTenantBase):
    id: UUID
    document_id: UUID
    property_id: UUID | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


# Parsed Document Models
class ParsedDocumentBase(BaseModel):
    filename: str
    document_type: DocumentType = DocumentType.OTHER


class ParsedDocumentResponse(BaseModel):
    id: UUID
    user_id: UUID
    property_id: UUID | None = None
    project_id: UUID | None = None
    filename: str
    file_size: int
    mime_type: str
    page_count: int | None = None
    document_type: DocumentType
    confidence_score: float | None = None
    status: DocumentStatus
    error_message: str | None = None
    extracted_data: dict | None = None
    is_archived: bool = False
    created_at: datetime
    processed_at: datetime | None = None

    model_config = {"from_attributes": True}


class ParsedDocumentDetailResponse(ParsedDocumentResponse):
    available_spaces: list[AvailableSpaceResponse] = []
    existing_tenants: list[ExistingTenantResponse] = []


class DocumentListResponse(BaseModel):
    items: list[ParsedDocumentResponse]
    total: int
    page: int
    page_size: int


# Document Upload Response
class DocumentUploadResponse(BaseModel):
    id: UUID
    filename: str
    status: DocumentStatus
    message: str


# Extracted Flyer Data (intermediate representation)
class ExtractedPropertyInfo(BaseModel):
    """Property information extracted from a leasing flyer."""
    name: str | None = None
    address: str | None = None
    city: str | None = None
    state: str | None = None
    zip_code: str | None = None
    property_type: str | None = None
    total_sf: int | None = None
    year_built: int | None = None
    parking_ratio: str | None = None
    landlord_name: str | None = None


class ExtractedAvailableSpace(BaseModel):
    """Available space extracted from a leasing flyer."""
    suite_number: str | None = None
    building_address: str | None = None
    square_footage: int | None = None
    min_divisible_sf: int | None = None
    asking_rent_psf: float | None = None
    rent_type: str | None = None
    is_endcap: bool = False
    is_anchor: bool = False
    has_drive_thru: bool = False
    has_patio: bool = False
    previous_tenant: str | None = None
    notes: str | None = None


class ExtractedTenant(BaseModel):
    """Existing tenant extracted from a leasing flyer."""
    name: str
    category: str | None = None
    suite_number: str | None = None
    square_footage: int | None = None
    is_anchor: bool = False
    is_national: bool = False


class ExtractedFlyerData(BaseModel):
    """Complete data extracted from a leasing flyer."""
    property_info: ExtractedPropertyInfo
    available_spaces: list[ExtractedAvailableSpace] = []
    existing_tenants: list[ExtractedTenant] = []
    amenities: list[str] = []
    highlights: list[str] = []
    contact_info: dict | None = None


# Site Plan Extracted Data Models
class SitePlanLocationArea(BaseModel):
    """A distinct area/zone within a site plan (building, pad, outparcel)."""
    name: str | None = None
    area_type: str | None = None  # building, pad, outparcel, parking
    square_footage: int | None = None
    tenant_name: str | None = None  # If occupied
    is_available: bool = False
    position_description: str | None = None  # e.g., "northwest corner", "inline"
    notes: str | None = None


class ExtractedSitePlanData(BaseModel):
    """Complete data extracted from a site plan/plot PDF."""
    property_info: ExtractedPropertyInfo
    location_areas: list[SitePlanLocationArea] = []
    tenant_locations: list[ExtractedTenant] = []  # Tenants with positions
    available_areas: list[SitePlanLocationArea] = []  # Vacant/available spaces
    total_site_sf: int | None = None
    parking_spaces: int | None = None
    parking_ratio: str | None = None
    site_dimensions: dict | None = None  # width, depth, etc.
    highlights: list[str] = []


# Start Analysis Response
class StartAnalysisResponse(BaseModel):
    """Response when starting void analysis from a document."""
    session_id: str
    property_address: str | None = None
    property_name: str | None = None
    tenant_count: int = 0
    available_space_count: int = 0
    document_type: DocumentType
    message: str = "Analysis session created successfully"


# Void Analysis Models
class VoidCategory(BaseModel):
    """A category in void analysis (e.g., Fast Casual, Boutique Fitness)."""
    category_name: str
    subcategory: str | None = None
    is_void: bool = True  # True if missing from trade area
    existing_count: int = 0
    market_count: int = 0
    match_score: float | None = None  # 0-100
    potential_tenants: list[str] = []
    notes: str | None = None


class VoidAnalysisCreate(BaseModel):
    property_id: str | None = None
    radius_miles: float = 3.0


class VoidAnalysisResponse(BaseModel):
    id: UUID
    document_id: UUID | None = None
    property_id: UUID | None = None
    user_id: UUID
    radius_miles: float | None = None
    analysis_date: datetime
    results: dict
    total_voids: int
    high_priority_voids: int
    created_at: datetime

    model_config = {"from_attributes": True}


# Investment Memo Models
class InvestmentMemoCreate(BaseModel):
    property_id: str | None = None
    title: str
    include_demographics: bool = True
    include_traffic: bool = True
    include_voids: bool = True
    include_tenant_interest: bool = True


class InvestmentMemoFinancials(BaseModel):
    irr: float | None = None
    rental_yield: float | None = None
    exit_cap_rate: float | None = None
    land_price: float | None = None
    total_investment: float | None = None
    noi: float | None = None
    asking_rent_psf: float | None = None
    rent_type: str | None = None


class InvestmentMemoResponse(BaseModel):
    id: UUID
    user_id: UUID
    property_id: UUID | None = None
    title: str
    version: int
    summary: str | None = None
    location_highlights: dict | None = None
    financials: dict | None = None
    demographics: dict | None = None
    tenant_interest: dict | None = None
    scope_of_work: str | None = None
    pdf_path: str | None = None
    is_draft: bool
    shared_with: list[str] | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class InvestmentMemoUpdate(BaseModel):
    title: str | None = None
    summary: str | None = None
    location_highlights: dict | None = None
    financials: dict | None = None
    demographics: dict | None = None
    tenant_interest: dict | None = None
    scope_of_work: str | None = None
    is_draft: bool | None = None
