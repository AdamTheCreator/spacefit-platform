"""Pydantic schemas for the contacts directory (companies + contacts).

Enum-ish fields are kept as ``Literal`` strings so they validate cleanly while
the DB columns stay plain ``VARCHAR`` (no native-enum cast surprises). Email is
a plain ``str`` rather than ``EmailStr`` so messy CSV imports don't hard-fail a
whole row on a malformed address.
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel

VerificationStatus = Literal["verified", "unverified", "stale", "bounced"]
ContactSource = Literal["apollo", "linkedin", "costar_import", "manual"]
InteractionType = Literal["meeting", "note", "enrich", "email_in", "email_out"]


# --------------------------------------------------------------------------- #
# Companies
# --------------------------------------------------------------------------- #
class CompanyBase(BaseModel):
    name: str
    sector: str | None = None
    subsector: str | None = None
    us_locations: int | None = None
    is_expanding: bool | None = None
    target_markets: list[str] | None = None
    sf_min: int | None = None
    sf_max: int | None = None
    website: str | None = None
    criteria: dict | None = None
    notes: str | None = None


class CompanyCreate(CompanyBase):
    pass


class CompanyUpdate(BaseModel):
    name: str | None = None
    sector: str | None = None
    subsector: str | None = None
    us_locations: int | None = None
    is_expanding: bool | None = None
    target_markets: list[str] | None = None
    sf_min: int | None = None
    sf_max: int | None = None
    website: str | None = None
    criteria: dict | None = None
    notes: str | None = None


class CompanyResponse(CompanyBase):
    id: str
    enriched_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# --------------------------------------------------------------------------- #
# Contacts
# --------------------------------------------------------------------------- #
class ContactBase(BaseModel):
    first: str
    last: str | None = None
    role: str | None = None
    email: str | None = None
    phone: str | None = None
    verif: VerificationStatus = "unverified"
    source: ContactSource = "manual"
    linkedin: bool = False
    notes: str | None = None


class ContactCreate(ContactBase):
    # Attach to an existing company, or auto-create one by name.
    company_id: str | None = None
    company_name: str | None = None


class ContactUpdate(BaseModel):
    first: str | None = None
    last: str | None = None
    role: str | None = None
    email: str | None = None
    phone: str | None = None
    verif: VerificationStatus | None = None
    source: ContactSource | None = None
    linkedin: bool | None = None
    notes: str | None = None
    company_id: str | None = None


class ContactResponse(ContactBase):
    id: str
    company_id: str
    last_verified_at: datetime | None = None
    last_contacted_at: datetime | None = None
    last_reply_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# --------------------------------------------------------------------------- #
# Interactions
# --------------------------------------------------------------------------- #
class InteractionCreate(BaseModel):
    type: InteractionType = "note"
    summary: str
    who: str | None = None
    title: str | None = None
    occurred_at: datetime | None = None


class InteractionResponse(BaseModel):
    id: str
    contact_id: str
    type: str
    occurred_at: datetime
    who: str | None = None
    title: str | None = None
    summary: str
    created_at: datetime

    model_config = {"from_attributes": True}


# --------------------------------------------------------------------------- #
# Collections
# --------------------------------------------------------------------------- #
class CompanyListResponse(BaseModel):
    items: list[CompanyResponse]
    total: int
    page: int
    page_size: int
    pages: int


class ContactListResponse(BaseModel):
    items: list[ContactResponse]
    total: int
    page: int
    page_size: int
    pages: int


class ContactImportResult(BaseModel):
    imported: int
    failed: int
    companies_created: int
    errors: list[str]
