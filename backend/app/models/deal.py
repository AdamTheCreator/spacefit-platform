from datetime import date, datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field


class DealStage(str, Enum):
    LEAD = "lead"
    TOUR = "tour"
    LOI = "loi"
    LEASE = "lease"
    CLOSED = "closed"
    LOST = "lost"


class DealType(str, Enum):
    LEASE = "lease"
    SALE = "sale"
    SUBLEASE = "sublease"


class ActivityType(str, Enum):
    NOTE = "note"
    CALL = "call"
    EMAIL = "email"
    MEETING = "meeting"
    TOUR = "tour"
    DOCUMENT = "document"


# Property Models
class PropertyBase(BaseModel):
    name: str
    address: str
    city: str
    state: str
    zip_code: str
    latitude: float | None = None
    longitude: float | None = None
    property_type: str = "retail"
    total_sf: int | None = None
    available_sf: int | None = None
    landlord_id: str | None = None
    notes: str | None = None


class PropertyCreate(PropertyBase):
    pass


class PropertyUpdate(BaseModel):
    name: str | None = None
    address: str | None = None
    city: str | None = None
    state: str | None = None
    zip_code: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    property_type: str | None = None
    total_sf: int | None = None
    available_sf: int | None = None
    landlord_id: str | None = None
    notes: str | None = None


class PropertyResponse(PropertyBase):
    id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# Deal Activity Models
class DealActivityBase(BaseModel):
    activity_type: ActivityType = ActivityType.NOTE
    title: str
    description: str | None = None
    scheduled_at: datetime | None = None
    completed_at: datetime | None = None


class DealActivityCreate(DealActivityBase):
    pass


class DealActivityResponse(DealActivityBase):
    id: UUID
    deal_id: UUID
    user_id: UUID
    created_at: datetime

    model_config = {"from_attributes": True}


# Deal Stage History Models
class DealStageHistoryResponse(BaseModel):
    id: UUID
    deal_id: UUID
    from_stage: DealStage | None
    to_stage: DealStage
    changed_by: UUID
    changed_at: datetime
    notes: str | None = None

    model_config = {"from_attributes": True}


# Deal Models
class DealBase(BaseModel):
    name: str
    stage: DealStage = DealStage.LEAD
    deal_type: DealType = DealType.LEASE
    property_id: str | None = None
    customer_id: str | None = None
    asking_rent_psf: float | None = None
    negotiated_rent_psf: float | None = None
    square_footage: int | None = None
    commission_rate: float | None = None
    commission_amount: float | None = None
    probability: int = Field(default=50, ge=0, le=100)
    expected_close_date: date | None = None
    actual_close_date: date | None = None
    lease_start_date: date | None = None
    lease_term_months: int | None = None
    source: str | None = None
    notes: str | None = None


class DealCreate(DealBase):
    pass


class DealUpdate(BaseModel):
    name: str | None = None
    stage: DealStage | None = None
    deal_type: DealType | None = None
    property_id: str | None = None
    customer_id: str | None = None
    asking_rent_psf: float | None = None
    negotiated_rent_psf: float | None = None
    square_footage: int | None = None
    commission_rate: float | None = None
    commission_amount: float | None = None
    probability: int | None = Field(default=None, ge=0, le=100)
    expected_close_date: date | None = None
    actual_close_date: date | None = None
    lease_start_date: date | None = None
    lease_term_months: int | None = None
    source: str | None = None
    notes: str | None = None
    is_archived: bool | None = None


class DealStageUpdate(BaseModel):
    stage: DealStage
    notes: str | None = None


class DealResponse(DealBase):
    id: UUID
    user_id: UUID
    is_archived: bool
    created_at: datetime
    updated_at: datetime
    property: PropertyResponse | None = None
    customer_name: str | None = None  # Populated from customer relationship

    model_config = {"from_attributes": True}


class DealDetailResponse(DealResponse):
    stage_history: list[DealStageHistoryResponse] = []
    activities: list[DealActivityResponse] = []


class DealListResponse(BaseModel):
    items: list[DealResponse]
    total: int
    page: int
    page_size: int
    pages: int


# Pipeline Summary Models
class StageSummary(BaseModel):
    stage: DealStage
    count: int
    total_commission: float


class PipelineSummary(BaseModel):
    stages: list[StageSummary]
    total_deals: int
    total_potential_commission: float


# Commission Forecast Models
class MonthlyForecast(BaseModel):
    month: str  # "2026-01"
    expected_commission: float
    deal_count: int


class CommissionForecast(BaseModel):
    forecast: list[MonthlyForecast]
    total_forecast: float


# Calendar View Models
class DealCalendarItem(BaseModel):
    id: UUID
    name: str
    stage: DealStage
    date: date
    date_type: str  # "expected_close", "lease_start", "actual_close"
    commission_amount: float | None

    model_config = {"from_attributes": True}
