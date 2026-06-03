"""Pydantic schemas for property listings + the client-fit matching engine.

``asset_type`` / ``source`` are kept as plain ``str`` (validated, not native
PG enum) to match the model columns and survive messy CSV imports. The matching
schemas (``MatchRequest`` / ``MatchedListing`` / ``MatchResponse``) shape the
``POST /listings/match`` request + LLM-scored response.
"""

from datetime import datetime

from pydantic import BaseModel


# --------------------------------------------------------------------------- #
# Listings
# --------------------------------------------------------------------------- #
class ListingBase(BaseModel):
    address: str | None = None
    city: str | None = None
    state: str | None = None
    zip_code: str | None = None
    asset_type: str | None = None
    size_sf: int | None = None
    price: int | None = None
    cap_rate: float | None = None
    year_built: int | None = None
    units: int | None = None
    listing_url: str | None = None
    description: str | None = None


class ListingCreate(ListingBase):
    source: str = "manual"
    raw: dict | None = None


class ListingResponse(ListingBase):
    id: str
    source: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ListingListResponse(BaseModel):
    items: list[ListingResponse]
    total: int
    page: int
    page_size: int
    pages: int


class ListingImportResult(BaseModel):
    imported: int
    failed: int
    errors: list[str]


# --------------------------------------------------------------------------- #
# Client-fit matching
# --------------------------------------------------------------------------- #
class MatchRequest(BaseModel):
    company_id: str
    limit: int = 50


class MatchedListing(BaseModel):
    listing: ListingResponse
    fit_score: int
    rationale: str
    flags: list[str]


class MatchResponse(BaseModel):
    client_name: str
    matches: list[MatchedListing]
