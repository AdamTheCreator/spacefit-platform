"""Contacts directory API — companies, contacts, and an interaction timeline.

Real per-user replacement for the old hardcoded frontend directory. Supports
CSV/XLSX bulk import (companies are de-duplicated by name within a user) and
single create/update/delete for both companies and contacts.
"""

import io
from datetime import datetime
from typing import Annotated

import pandas as pd
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, get_db
from app.db.models.contact import Company, Contact, ContactInteraction
from app.models.contact import (
    CompanyCreate,
    CompanyListResponse,
    CompanyResponse,
    CompanyUpdate,
    ContactCreate,
    ContactImportResult,
    ContactListResponse,
    ContactResponse,
    ContactUpdate,
    InteractionCreate,
    InteractionResponse,
)

router = APIRouter(tags=["contacts"])


# --------------------------------------------------------------------------- #
# Companies
# --------------------------------------------------------------------------- #
@router.get("/companies", response_model=CompanyListResponse)
async def list_companies(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    page: int = Query(1, ge=1),
    page_size: int = Query(200, ge=1, le=1000),
    search: str | None = None,
    sector: str | None = None,
    is_expanding: bool | None = None,
) -> CompanyListResponse:
    """List the current user's companies with search + filters."""
    query = select(Company).where(Company.user_id == current_user.id)
    if search:
        query = query.where(Company.name.ilike(f"%{search}%"))
    if sector:
        query = query.where(Company.sector == sector)
    if is_expanding is not None:
        query = query.where(Company.is_expanding == is_expanding)

    total = (
        await db.execute(select(func.count()).select_from(query.subquery()))
    ).scalar() or 0

    query = (
        query.order_by(Company.name)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    rows = (await db.execute(query)).scalars().all()
    pages = (total + page_size - 1) // page_size
    return CompanyListResponse(
        items=[CompanyResponse.model_validate(c) for c in rows],
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )


@router.post(
    "/companies",
    response_model=CompanyResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_company(
    data: CompanyCreate,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CompanyResponse:
    """Create a company."""
    company = Company(user_id=current_user.id, **data.model_dump())
    db.add(company)
    await db.commit()
    await db.refresh(company)
    return CompanyResponse.model_validate(company)


async def _get_company(
    db: AsyncSession, user_id: str, company_id: str
) -> Company:
    company = (
        await db.execute(
            select(Company).where(
                Company.id == company_id, Company.user_id == user_id
            )
        )
    ).scalar_one_or_none()
    if company is None:
        raise HTTPException(status_code=404, detail="Company not found")
    return company


@router.get("/companies/{company_id}", response_model=CompanyResponse)
async def get_company(
    company_id: str,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CompanyResponse:
    """Get one company."""
    company = await _get_company(db, current_user.id, company_id)
    return CompanyResponse.model_validate(company)


@router.patch("/companies/{company_id}", response_model=CompanyResponse)
async def update_company(
    company_id: str,
    data: CompanyUpdate,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CompanyResponse:
    """Patch a company (only provided fields change)."""
    company = await _get_company(db, current_user.id, company_id)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(company, field, value)
    await db.commit()
    await db.refresh(company)
    return CompanyResponse.model_validate(company)


@router.delete(
    "/companies/{company_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def delete_company(
    company_id: str,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """Delete a company (cascades to its contacts)."""
    company = await _get_company(db, current_user.id, company_id)
    await db.delete(company)
    await db.commit()


# --------------------------------------------------------------------------- #
# Contacts
# --------------------------------------------------------------------------- #
@router.get("/contacts", response_model=ContactListResponse)
async def list_contacts(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    page: int = Query(1, ge=1),
    page_size: int = Query(500, ge=1, le=1000),
    search: str | None = None,
    company_id: str | None = None,
    verif: str | None = None,
) -> ContactListResponse:
    """List the current user's contacts with search + filters."""
    query = select(Contact).where(Contact.user_id == current_user.id)
    if company_id:
        query = query.where(Contact.company_id == company_id)
    if verif:
        query = query.where(Contact.verif == verif)
    if search:
        like = f"%{search}%"
        query = query.where(
            Contact.first.ilike(like)
            | Contact.last.ilike(like)
            | Contact.email.ilike(like)
            | Contact.role.ilike(like)
        )

    total = (
        await db.execute(select(func.count()).select_from(query.subquery()))
    ).scalar() or 0

    query = (
        query.order_by(Contact.first)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    rows = (await db.execute(query)).scalars().all()
    pages = (total + page_size - 1) // page_size
    return ContactListResponse(
        items=[ContactResponse.model_validate(c) for c in rows],
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )


async def _resolve_company_id(
    db: AsyncSession,
    user_id: str,
    company_id: str | None,
    company_name: str | None,
) -> str:
    """Return a valid company id for this user, creating one by name if needed."""
    if company_id:
        await _get_company(db, user_id, company_id)  # validates ownership
        return company_id
    name = (company_name or "").strip() or "Unassigned"
    existing = (
        await db.execute(
            select(Company).where(
                Company.user_id == user_id,
                func.lower(Company.name) == name.lower(),
            )
        )
    ).scalar_one_or_none()
    if existing:
        return existing.id
    company = Company(user_id=user_id, name=name)
    db.add(company)
    await db.flush()
    return company.id


@router.post(
    "/contacts",
    response_model=ContactResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_contact(
    data: ContactCreate,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ContactResponse:
    """Create a contact under an existing or newly-named company."""
    payload = data.model_dump()
    company_id = payload.pop("company_id", None)
    company_name = payload.pop("company_name", None)
    resolved = await _resolve_company_id(
        db, current_user.id, company_id, company_name
    )
    contact = Contact(user_id=current_user.id, company_id=resolved, **payload)
    db.add(contact)
    await db.commit()
    await db.refresh(contact)
    return ContactResponse.model_validate(contact)


@router.post("/contacts/import", response_model=ContactImportResult)
async def import_contacts(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    file: UploadFile = File(...),
) -> ContactImportResult:
    """Bulk-import contacts (+ companies) from a CSV or Excel file."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")
    fn = file.filename.lower()
    if not (fn.endswith(".csv") or fn.endswith(".xlsx")):
        raise HTTPException(
            status_code=400, detail="File must be CSV or Excel (.xlsx)"
        )

    content = await file.read()
    try:
        if fn.endswith(".csv"):
            df = pd.read_csv(io.BytesIO(content))
        else:
            df = pd.read_excel(io.BytesIO(content))
    except Exception as e:  # noqa: BLE001 - surface any parse failure to the user
        raise HTTPException(status_code=400, detail=f"Failed to parse file: {e}")

    df.columns = df.columns.str.lower().str.strip()
    aliases = {
        "first": ["first", "first_name", "firstname"],
        "last": ["last", "last_name", "lastname", "surname"],
        "name": ["name", "full_name", "contact", "contact_name"],
        "company": ["company", "company_name", "brand", "organization", "account"],
        "email": ["email", "email_address", "e-mail"],
        "phone": ["phone", "phone_number", "telephone", "mobile"],
        "role": ["role", "title", "job_title", "position"],
        "sector": ["sector", "industry", "category"],
        "website": ["website", "url", "web"],
    }
    col: dict[str, str] = {}
    for field, names in aliases.items():
        for n in names:
            if n in df.columns:
                col[field] = n
                break

    def cell(row, field: str) -> str | None:
        c = col.get(field)
        if not c:
            return None
        v = row.get(c)
        if v is None or (isinstance(v, float) and pd.isna(v)):
            return None
        return str(v).strip() or None

    # Preload existing companies so the import de-dupes by name.
    existing = (
        await db.execute(select(Company).where(Company.user_id == current_user.id))
    ).scalars().all()
    by_name = {c.name.lower(): c for c in existing}

    imported = failed = companies_created = 0
    errors: list[str] = []

    for idx, row in df.iterrows():
        try:
            first = cell(row, "first")
            last = cell(row, "last")
            if not first and not last:
                full = cell(row, "name")
                if full:
                    parts = full.split()
                    first = parts[0]
                    last = " ".join(parts[1:]) or None
            email = cell(row, "email")
            if not first and not email:
                failed += 1
                errors.append(f"Row {idx + 2}: missing name and email")
                continue

            company_name = cell(row, "company") or "Unassigned"
            key = company_name.lower()
            company = by_name.get(key)
            if company is None:
                company = Company(
                    user_id=current_user.id,
                    name=company_name,
                    sector=cell(row, "sector"),
                    website=cell(row, "website"),
                )
                db.add(company)
                await db.flush()
                by_name[key] = company
                companies_created += 1

            contact = Contact(
                user_id=current_user.id,
                company_id=company.id,
                first=first or email or "Unknown",
                last=last,
                role=cell(row, "role"),
                email=email,
                phone=cell(row, "phone"),
                source="manual",
            )
            db.add(contact)
            imported += 1
        except Exception as e:  # noqa: BLE001 - per-row failure shouldn't abort all
            failed += 1
            errors.append(f"Row {idx + 2}: {e}")

    await db.commit()
    return ContactImportResult(
        imported=imported,
        failed=failed,
        companies_created=companies_created,
        errors=errors[:10],
    )


async def _get_contact(
    db: AsyncSession, user_id: str, contact_id: str
) -> Contact:
    contact = (
        await db.execute(
            select(Contact).where(
                Contact.id == contact_id, Contact.user_id == user_id
            )
        )
    ).scalar_one_or_none()
    if contact is None:
        raise HTTPException(status_code=404, detail="Contact not found")
    return contact


@router.get("/contacts/{contact_id}", response_model=ContactResponse)
async def get_contact(
    contact_id: str,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ContactResponse:
    """Get one contact."""
    contact = await _get_contact(db, current_user.id, contact_id)
    return ContactResponse.model_validate(contact)


@router.patch("/contacts/{contact_id}", response_model=ContactResponse)
async def update_contact(
    contact_id: str,
    data: ContactUpdate,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ContactResponse:
    """Patch a contact (only provided fields change)."""
    contact = await _get_contact(db, current_user.id, contact_id)
    updates = data.model_dump(exclude_unset=True)
    if updates.get("company_id"):
        await _get_company(db, current_user.id, updates["company_id"])
    for field, value in updates.items():
        setattr(contact, field, value)
    await db.commit()
    await db.refresh(contact)
    return ContactResponse.model_validate(contact)


@router.delete(
    "/contacts/{contact_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def delete_contact(
    contact_id: str,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """Delete a contact."""
    contact = await _get_contact(db, current_user.id, contact_id)
    await db.delete(contact)
    await db.commit()


# --------------------------------------------------------------------------- #
# Interaction timeline
# --------------------------------------------------------------------------- #
@router.get(
    "/contacts/{contact_id}/interactions",
    response_model=list[InteractionResponse],
)
async def list_interactions(
    contact_id: str,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[InteractionResponse]:
    """List a contact's interaction timeline, newest first."""
    await _get_contact(db, current_user.id, contact_id)  # ownership check
    rows = (
        await db.execute(
            select(ContactInteraction)
            .where(
                ContactInteraction.contact_id == contact_id,
                ContactInteraction.user_id == current_user.id,
            )
            .order_by(ContactInteraction.occurred_at.desc())
        )
    ).scalars().all()
    return [InteractionResponse.model_validate(r) for r in rows]


@router.post(
    "/contacts/{contact_id}/interactions",
    response_model=InteractionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_interaction(
    contact_id: str,
    data: InteractionCreate,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> InteractionResponse:
    """Add a note / meeting / etc. to a contact's timeline."""
    await _get_contact(db, current_user.id, contact_id)
    interaction = ContactInteraction(
        contact_id=contact_id,
        user_id=current_user.id,
        type=data.type,
        summary=data.summary,
        who=data.who,
        title=data.title,
        occurred_at=data.occurred_at or datetime.utcnow(),
    )
    db.add(interaction)
    await db.commit()
    await db.refresh(interaction)
    return InteractionResponse.model_validate(interaction)
