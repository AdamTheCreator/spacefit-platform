import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def utc_now() -> datetime:
    return datetime.utcnow()


def uuid_str() -> str:
    return str(uuid.uuid4())


class SalesLeadStatus(str, enum.Enum):
    NEW = "new"
    CONTACTED = "contacted"
    QUALIFIED = "qualified"
    DISQUALIFIED = "disqualified"
    CLOSED_WON = "closed_won"
    CLOSED_LOST = "closed_lost"


class SalesLead(Base):
    """Inbound enterprise / sales inquiry captured from the pricing page.

    These rows are written by the public ``POST /sales/leads`` endpoint
    and reviewed by an admin. We deliberately keep this independent of
    the ``users`` table so prospects can submit a lead without first
    creating an account; when an authenticated user does submit, we
    populate ``user_id`` so the admin tooling can link back.
    """

    __tablename__ = "sales_leads"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    company_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    team_size: Mapped[str | None] = mapped_column(String(20), nullable=True)
    current_tools: Mapped[str | None] = mapped_column(Text, nullable=True)
    use_case: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str] = mapped_column(String(50), default="pricing_page")
    status: Mapped[SalesLeadStatus] = mapped_column(
        Enum(
            SalesLeadStatus,
            name="sales_lead_status",
            native_enum=False,
            length=30,
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
        ),
        default=SalesLeadStatus.NEW,
    )
    user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    contacted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utc_now, onupdate=utc_now
    )
