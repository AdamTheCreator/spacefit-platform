import uuid
from datetime import date, datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models.customer import Customer
    from app.db.models.document import ParsedDocument
    from app.db.models.user import User


def utc_now() -> datetime:
    return datetime.utcnow()


def uuid_str() -> str:
    return str(uuid.uuid4())


class DealStage(str, Enum):
    INTAKE = "intake"
    QUALIFICATION = "qualification"
    DUE_DILIGENCE = "due_diligence"
    TENANT_VETTING = "tenant_vetting"
    LOI = "loi"
    UNDER_CONTRACT = "under_contract"
    CLOSED = "closed"
    PASSED = "passed"
    DEAD = "dead"


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


class Property(Base):
    """Commercial property that can be associated with deals."""
    __tablename__ = "properties"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    address: Mapped[str] = mapped_column(String(500), nullable=False)
    city: Mapped[str] = mapped_column(String(100), nullable=False)
    state: Mapped[str] = mapped_column(String(50), nullable=False)
    zip_code: Mapped[str] = mapped_column(String(20), nullable=False)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    property_type: Mapped[str] = mapped_column(String(50), default="retail")  # retail, office, industrial
    total_sf: Mapped[int | None] = mapped_column(Integer, nullable=True)
    available_sf: Mapped[int | None] = mapped_column(Integer, nullable=True)
    landlord_id: Mapped[str | None] = mapped_column(String(36), nullable=True)  # FK to landlords
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Market classification
    market_region: Mapped[str | None] = mapped_column(String(10), nullable=True)
    metro_area: Mapped[str | None] = mapped_column(String(100), nullable=True)
    product_type: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Qualification
    intersection_quality: Mapped[str | None] = mapped_column(String(50), nullable=True)
    traffic_count_vpd: Mapped[int | None] = mapped_column(Integer, nullable=True)
    population_1mi: Mapped[int | None] = mapped_column(Integer, nullable=True)
    population_3mi: Mapped[int | None] = mapped_column(Integer, nullable=True)
    population_5mi: Mapped[int | None] = mapped_column(Integer, nullable=True)
    median_hhi_3mi: Mapped[float | None] = mapped_column(Float, nullable=True)
    qualification_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    qualification_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Ownership & Zoning
    owner_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    owner_entity: Mapped[str | None] = mapped_column(String(255), nullable=True)
    zoning_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    zoning_description: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Pricing (for comps)
    asking_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    cap_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    price_psf: Mapped[float | None] = mapped_column(Float, nullable=True)
    noi: Mapped[float | None] = mapped_column(Float, nullable=True)
    is_sale_comp: Mapped[bool] = mapped_column(Boolean, default=False)

    # Broker contact
    broker_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    broker_company: Mapped[str | None] = mapped_column(String(255), nullable=True)
    broker_phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    broker_email: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Source tracking
    source_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    source_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now)

    # Relationships
    user: Mapped["User"] = relationship(back_populates="properties")
    deals: Mapped[list["Deal"]] = relationship(back_populates="property")
    documents: Mapped[list["ParsedDocument"]] = relationship(back_populates="property")


class Deal(Base):
    """A deal in the pipeline - tracks a potential lease/sale through stages."""
    __tablename__ = "deals"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    property_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("properties.id", ondelete="SET NULL"), nullable=True
    )
    customer_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("customers.id", ondelete="SET NULL"), nullable=True
    )

    # Deal info
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    stage: Mapped[str] = mapped_column(String(20), default=DealStage.INTAKE.value)
    deal_type: Mapped[str] = mapped_column(String(20), default=DealType.LEASE.value)

    # Financials
    asking_rent_psf: Mapped[float | None] = mapped_column(Float, nullable=True)
    negotiated_rent_psf: Mapped[float | None] = mapped_column(Float, nullable=True)
    square_footage: Mapped[int | None] = mapped_column(Integer, nullable=True)
    commission_rate: Mapped[float | None] = mapped_column(Float, nullable=True)  # percentage (e.g., 5.0 = 5%)
    commission_amount: Mapped[float | None] = mapped_column(Float, nullable=True)  # calculated or manual

    # Timeline
    probability: Mapped[int] = mapped_column(Integer, default=50)  # 0-100%
    expected_close_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    actual_close_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    lease_start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    lease_term_months: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Metadata
    source: Mapped[str | None] = mapped_column(String(100), nullable=True)  # referral, cold_call, inbound
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now)

    # Relationships
    user: Mapped["User"] = relationship(back_populates="deals")
    property: Mapped["Property | None"] = relationship(back_populates="deals")
    customer: Mapped["Customer | None"] = relationship(back_populates="deals")
    stage_history: Mapped[list["DealStageHistory"]] = relationship(
        back_populates="deal", cascade="all, delete-orphan", order_by="DealStageHistory.changed_at.desc()"
    )
    activities: Mapped[list["DealActivity"]] = relationship(
        back_populates="deal", cascade="all, delete-orphan", order_by="DealActivity.created_at.desc()"
    )


class DealStageHistory(Base):
    """Tracks stage transitions for a deal."""
    __tablename__ = "deal_stage_history"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    deal_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("deals.id", ondelete="CASCADE"), nullable=False
    )
    from_stage: Mapped[str | None] = mapped_column(String(20), nullable=True)  # null for initial creation
    to_stage: Mapped[str] = mapped_column(String(20), nullable=False)
    changed_by: Mapped[str] = mapped_column(String(36), nullable=False)  # user_id
    changed_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    deal: Mapped["Deal"] = relationship(back_populates="stage_history")


class DealActivity(Base):
    """Activity log for a deal - notes, calls, emails, meetings, etc."""
    __tablename__ = "deal_activities"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    deal_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("deals.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[str] = mapped_column(String(36), nullable=False)
    activity_type: Mapped[str] = mapped_column(String(20), default=ActivityType.NOTE.value)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)

    # Relationships
    deal: Mapped["Deal"] = relationship(back_populates="activities")
