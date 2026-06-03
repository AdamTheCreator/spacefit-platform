"""Property listings API + the client-fit matching engine.

CRUD + CSV/XLSX import for imported CRE for-sale listings, plus
``POST /listings/match`` which scores a user's listings against a client
``Company``'s buy-box with the LLM (the inverse of the void/matchmaker flow)
and returns them ranked by fit. User-scoped throughout: every query filters by
``user_id``, and matching validates the target company belongs to the caller.
"""

import io
from typing import Annotated

import pandas as pd
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, get_db
from app.db.models.contact import Company
from app.db.models.listing import PropertyListing
from app.models.listing import (
    ListingCreate,
    ListingImportResult,
    ListingListResponse,
    ListingResponse,
    MatchedListing,
    MatchRequest,
    MatchResponse,
)
from app.services.listing_match import match_listings_for_client
from app.services.user_llm import resolve_user_llm

router = APIRouter(prefix="/listings", tags=["listings"])


# --------------------------------------------------------------------------- #
# CRUD
# --------------------------------------------------------------------------- #
@router.get("", response_model=ListingListResponse)
async def list_listings(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    page: int = Query(1, ge=1),
    page_size: int = Query(200, ge=1, le=1000),
    search: str | None = None,
    asset_type: str | None = None,
) -> ListingListResponse:
    """List the current user's listings with search + asset_type filter."""
    query = select(PropertyListing).where(
        PropertyListing.user_id == current_user.id
    )
    if asset_type:
        query = query.where(PropertyListing.asset_type == asset_type)
    if search:
        like = f"%{search}%"
        query = query.where(
            PropertyListing.address.ilike(like)
            | PropertyListing.city.ilike(like)
            | PropertyListing.state.ilike(like)
            | PropertyListing.description.ilike(like)
        )

    total = (
        await db.execute(select(func.count()).select_from(query.subquery()))
    ).scalar() or 0

    query = (
        query.order_by(PropertyListing.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    rows = (await db.execute(query)).scalars().all()
    pages = (total + page_size - 1) // page_size
    return ListingListResponse(
        items=[ListingResponse.model_validate(r) for r in rows],
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )


@router.post(
    "",
    response_model=ListingResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_listing(
    data: ListingCreate,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ListingResponse:
    """Create a single listing."""
    listing = PropertyListing(user_id=current_user.id, **data.model_dump())
    db.add(listing)
    await db.commit()
    await db.refresh(listing)
    return ListingResponse.model_validate(listing)


def _parse_int(value: object) -> int | None:
    """Coerce a messy cell to int, stripping ``$ , SF`` noise; ``None`` on fail."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    s = str(value).strip()
    if not s:
        return None
    s = (
        s.replace("$", "")
        .replace(",", "")
        .replace("SF", "")
        .replace("sf", "")
        .strip()
    )
    try:
        return int(float(s))
    except (TypeError, ValueError):
        return None


def _parse_float(value: object) -> float | None:
    """Coerce a messy cell to float, stripping ``% , $`` noise; ``None`` on fail."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    s = str(value).strip().replace("%", "").replace(",", "").replace("$", "").strip()
    if not s:
        return None
    try:
        return float(s)
    except (TypeError, ValueError):
        return None


@router.post("/import", response_model=ListingImportResult)
async def import_listings(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    file: UploadFile = File(...),
) -> ListingImportResult:
    """Bulk-import listings from a CSV or Excel file (fuzzy column mapping)."""
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
        "address": ["address", "street", "property_address", "addr", "location"],
        "city": ["city", "town", "municipality"],
        "state": ["state", "st", "province", "region"],
        "zip_code": ["zip_code", "zip", "zipcode", "postal_code", "postal"],
        "asset_type": [
            "asset_type",
            "asset type",
            "property_type",
            "type",
            "asset_class",
        ],
        "size_sf": ["size_sf", "size", "sf", "square_feet", "sqft", "building_sf"],
        "price": ["price", "asking_price", "list_price", "sale_price", "ask"],
        "cap_rate": ["cap_rate", "cap rate", "cap", "caprate"],
        "year_built": ["year_built", "year built", "built", "yr_built"],
        "units": ["units", "unit_count", "num_units", "no_units"],
        "listing_url": ["listing_url", "url", "link", "listing_link", "web"],
        "description": ["description", "notes", "remarks", "comments", "summary"],
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

    def num_cell(row, field: str):
        c = col.get(field)
        return row.get(c) if c else None

    imported = failed = 0
    errors: list[str] = []

    for idx, row in df.iterrows():
        try:
            raw = {
                k: (None if (isinstance(v, float) and pd.isna(v)) else v)
                for k, v in row.to_dict().items()
            }
            listing = PropertyListing(
                user_id=current_user.id,
                address=cell(row, "address"),
                city=cell(row, "city"),
                state=cell(row, "state"),
                zip_code=cell(row, "zip_code"),
                asset_type=cell(row, "asset_type"),
                size_sf=_parse_int(num_cell(row, "size_sf")),
                price=_parse_int(num_cell(row, "price")),
                cap_rate=_parse_float(num_cell(row, "cap_rate")),
                year_built=_parse_int(num_cell(row, "year_built")),
                units=_parse_int(num_cell(row, "units")),
                listing_url=cell(row, "listing_url"),
                description=cell(row, "description"),
                source="csv" if fn.endswith(".csv") else "xlsx",
                raw=raw,
            )
            db.add(listing)
            imported += 1
        except Exception as e:  # noqa: BLE001 - per-row failure shouldn't abort all
            failed += 1
            errors.append(f"Row {idx + 2}: {e}")

    await db.commit()
    return ListingImportResult(
        imported=imported, failed=failed, errors=errors[:10]
    )


async def _get_listing(
    db: AsyncSession, user_id: str, listing_id: str
) -> PropertyListing:
    listing = (
        await db.execute(
            select(PropertyListing).where(
                PropertyListing.id == listing_id,
                PropertyListing.user_id == user_id,
            )
        )
    ).scalar_one_or_none()
    if listing is None:
        raise HTTPException(status_code=404, detail="Listing not found")
    return listing


@router.delete(
    "/{listing_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def delete_listing(
    listing_id: str,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """Delete a listing."""
    listing = await _get_listing(db, current_user.id, listing_id)
    await db.delete(listing)
    await db.commit()


# --------------------------------------------------------------------------- #
# Client-fit matching
# --------------------------------------------------------------------------- #
@router.post("/match", response_model=MatchResponse)
async def match_listings(
    data: MatchRequest,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> MatchResponse:
    """Score the user's listings against a client company's buy-box.

    Flow: load the client ``Company`` (404 unless it belongs to the caller) →
    load the user's listings (capped by ``limit``) → resolve the user's LLM
    (BYOK-aware) → score in one LLM call → join scores back to the listing
    rows and sort by ``fit_score`` desc.
    """
    company = (
        await db.execute(
            select(Company).where(
                Company.id == data.company_id,
                Company.user_id == current_user.id,
            )
        )
    ).scalar_one_or_none()
    if company is None:
        raise HTTPException(status_code=404, detail="Company not found")

    limit = max(1, min(data.limit, 50))
    rows = (
        await db.execute(
            select(PropertyListing)
            .where(PropertyListing.user_id == current_user.id)
            .order_by(PropertyListing.created_at.desc())
            .limit(limit)
        )
    ).scalars().all()

    if not rows:
        return MatchResponse(client_name=company.name, matches=[])

    # BYOK-aware: route through the user's resolved LLM (same as chat), so a
    # configured key keeps the zero-platform-tokens guarantee. Fall back to the
    # platform default if resolution fails for any reason.
    try:
        resolved_llm = await resolve_user_llm(db, current_user.id, current_user.tier)
    except Exception:  # noqa: BLE001 - never block scoring on resolution failure
        resolved_llm = None

    scores = await match_listings_for_client(company, list(rows), resolved_llm)

    by_id = {r.id: r for r in rows}
    matches: list[MatchedListing] = []
    for score in scores:
        listing = by_id.get(score["listing_id"])
        if listing is None:
            continue
        matches.append(
            MatchedListing(
                listing=ListingResponse.model_validate(listing),
                fit_score=score["fit_score"],
                rationale=score["rationale"],
                flags=score["flags"],
            )
        )

    matches.sort(key=lambda m: m.fit_score, reverse=True)
    return MatchResponse(client_name=company.name, matches=matches)
