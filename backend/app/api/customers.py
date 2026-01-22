import io
from typing import Annotated
from uuid import UUID

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_db, CurrentUser
from app.db.models.customer import Customer, CustomerContact
from app.models.customer import (
    CustomerCreate,
    CustomerUpdate,
    CustomerResponse,
    CustomerListResponse,
    CustomerImportResult,
)

router = APIRouter(prefix="/customers", tags=["customers"])


@router.get("", response_model=CustomerListResponse)
async def list_customers(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: str | None = None,
    is_active: bool | None = None,
) -> CustomerListResponse:
    """List customers with pagination and optional filtering."""
    query = select(Customer).where(Customer.user_id == current_user.id)

    if search:
        search_filter = f"%{search}%"
        query = query.where(
            Customer.name.ilike(search_filter)
            | Customer.company_name.ilike(search_filter)
            | Customer.email.ilike(search_filter)
        )

    if is_active is not None:
        query = query.where(Customer.is_active == is_active)

    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    query = (
        query.options(selectinload(Customer.contacts))
        .order_by(Customer.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )

    result = await db.execute(query)
    customers = result.scalars().all()

    pages = (total + page_size - 1) // page_size

    return CustomerListResponse(
        items=[CustomerResponse.model_validate(c) for c in customers],
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )


@router.post("", response_model=CustomerResponse, status_code=status.HTTP_201_CREATED)
async def create_customer(
    customer_data: CustomerCreate,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CustomerResponse:
    """Create a new customer."""
    customer = Customer(
        user_id=current_user.id,
        name=customer_data.name,
        company_name=customer_data.company_name,
        email=customer_data.email,
        phone=customer_data.phone,
        address_line1=customer_data.address_line1,
        address_line2=customer_data.address_line2,
        city=customer_data.city,
        state=customer_data.state,
        zip_code=customer_data.zip_code,
        country=customer_data.country,
        criteria=customer_data.criteria,
        notes=customer_data.notes,
        tags=customer_data.tags,
    )

    if customer_data.contacts:
        for contact_data in customer_data.contacts:
            contact = CustomerContact(
                name=contact_data.name,
                title=contact_data.title,
                email=contact_data.email,
                phone=contact_data.phone,
                is_primary=contact_data.is_primary,
            )
            customer.contacts.append(contact)

    db.add(customer)
    await db.commit()
    await db.refresh(customer)

    return CustomerResponse.model_validate(customer)


@router.get("/{customer_id}", response_model=CustomerResponse)
async def get_customer(
    customer_id: UUID,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CustomerResponse:
    """Get a customer by ID."""
    result = await db.execute(
        select(Customer)
        .options(selectinload(Customer.contacts))
        .where(Customer.id == customer_id, Customer.user_id == current_user.id)
    )
    customer = result.scalar_one_or_none()

    if customer is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Customer not found",
        )

    return CustomerResponse.model_validate(customer)


@router.put("/{customer_id}", response_model=CustomerResponse)
async def update_customer(
    customer_id: UUID,
    customer_data: CustomerUpdate,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CustomerResponse:
    """Update a customer."""
    result = await db.execute(
        select(Customer)
        .options(selectinload(Customer.contacts))
        .where(Customer.id == customer_id, Customer.user_id == current_user.id)
    )
    customer = result.scalar_one_or_none()

    if customer is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Customer not found",
        )

    update_data = customer_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(customer, field, value)

    await db.commit()
    await db.refresh(customer)

    return CustomerResponse.model_validate(customer)


@router.delete("/{customer_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_customer(
    customer_id: UUID,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """Delete a customer."""
    result = await db.execute(
        select(Customer).where(
            Customer.id == customer_id, Customer.user_id == current_user.id
        )
    )
    customer = result.scalar_one_or_none()

    if customer is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Customer not found",
        )

    await db.delete(customer)
    await db.commit()


@router.post("/import", response_model=CustomerImportResult)
async def import_customers(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    file: UploadFile = File(...),
) -> CustomerImportResult:
    """Import customers from CSV or Excel file."""
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No file provided",
        )

    filename = file.filename.lower()
    if not (filename.endswith(".csv") or filename.endswith(".xlsx")):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must be CSV or Excel (.xlsx)",
        )

    content = await file.read()

    try:
        if filename.endswith(".csv"):
            df = pd.read_csv(io.BytesIO(content))
        else:
            df = pd.read_excel(io.BytesIO(content))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to parse file: {str(e)}",
        )

    column_mapping = {
        "name": ["name", "customer_name", "customer", "company"],
        "company_name": ["company_name", "company", "organization"],
        "email": ["email", "email_address", "e-mail"],
        "phone": ["phone", "phone_number", "telephone"],
        "address_line1": ["address", "address_line1", "street", "address1"],
        "city": ["city"],
        "state": ["state", "province"],
        "zip_code": ["zip", "zip_code", "postal_code", "zipcode"],
    }

    df.columns = df.columns.str.lower().str.strip()

    mapped_columns = {}
    for field, possible_names in column_mapping.items():
        for col_name in possible_names:
            if col_name in df.columns:
                mapped_columns[field] = col_name
                break

    if "name" not in mapped_columns:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must have a 'name' column",
        )

    imported = 0
    failed = 0
    errors: list[str] = []

    for idx, row in df.iterrows():
        try:
            customer = Customer(
                user_id=current_user.id,
                name=str(row[mapped_columns["name"]]),
                company_name=str(row.get(mapped_columns.get("company_name", ""), "")) or None,
                email=str(row.get(mapped_columns.get("email", ""), "")) or None,
                phone=str(row.get(mapped_columns.get("phone", ""), "")) or None,
                address_line1=str(row.get(mapped_columns.get("address_line1", ""), "")) or None,
                city=str(row.get(mapped_columns.get("city", ""), "")) or None,
                state=str(row.get(mapped_columns.get("state", ""), "")) or None,
                zip_code=str(row.get(mapped_columns.get("zip_code", ""), "")) or None,
            )
            db.add(customer)
            imported += 1
        except Exception as e:
            failed += 1
            errors.append(f"Row {idx + 2}: {str(e)}")

    await db.commit()

    return CustomerImportResult(imported=imported, failed=failed, errors=errors[:10])


@router.get("/export/csv")
async def export_customers(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> StreamingResponse:
    """Export all customers to CSV."""
    result = await db.execute(
        select(Customer)
        .where(Customer.user_id == current_user.id)
        .order_by(Customer.name)
    )
    customers = result.scalars().all()

    data = []
    for c in customers:
        data.append({
            "name": c.name,
            "company_name": c.company_name,
            "email": c.email,
            "phone": c.phone,
            "address_line1": c.address_line1,
            "address_line2": c.address_line2,
            "city": c.city,
            "state": c.state,
            "zip_code": c.zip_code,
            "country": c.country,
            "notes": c.notes,
        })

    df = pd.DataFrame(data)
    output = io.StringIO()
    df.to_csv(output, index=False)
    output.seek(0)

    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=customers.csv"},
    )
