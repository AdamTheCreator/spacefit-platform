from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr


class CustomerContactBase(BaseModel):
    name: str
    title: str | None = None
    email: EmailStr | None = None
    phone: str | None = None
    is_primary: bool = False


class CustomerContactCreate(CustomerContactBase):
    pass


class CustomerContactResponse(CustomerContactBase):
    id: UUID
    created_at: datetime

    model_config = {"from_attributes": True}


class CustomerBase(BaseModel):
    name: str
    company_name: str | None = None
    email: EmailStr | None = None
    phone: str | None = None
    address_line1: str | None = None
    address_line2: str | None = None
    city: str | None = None
    state: str | None = None
    zip_code: str | None = None
    country: str = "USA"
    criteria: dict | None = None
    notes: str | None = None
    tags: list[str] | None = None


class CustomerCreate(CustomerBase):
    contacts: list[CustomerContactCreate] | None = None


class CustomerUpdate(BaseModel):
    name: str | None = None
    company_name: str | None = None
    email: EmailStr | None = None
    phone: str | None = None
    address_line1: str | None = None
    address_line2: str | None = None
    city: str | None = None
    state: str | None = None
    zip_code: str | None = None
    country: str | None = None
    criteria: dict | None = None
    notes: str | None = None
    tags: list[str] | None = None
    is_active: bool | None = None


class CustomerResponse(CustomerBase):
    id: UUID
    is_active: bool
    created_at: datetime
    updated_at: datetime
    contacts: list[CustomerContactResponse] = []

    model_config = {"from_attributes": True}


class CustomerListResponse(BaseModel):
    items: list[CustomerResponse]
    total: int
    page: int
    page_size: int
    pages: int


class CustomerImportResult(BaseModel):
    imported: int
    failed: int
    errors: list[str]
