"""Shared Pydantic schemas for normalized import data.

All parsers (CoStar CSV, Placer PDF, SiteUSA CSV) produce one of these
output types. The orchestrator and project context system consume them.
"""

from datetime import date
from pydantic import BaseModel


class TenantRecord(BaseModel):
    name: str
    suite: str | None = None
    square_feet: int | None = None
    rent_psf: float | None = None
    lease_start: date | None = None
    lease_end: date | None = None
    tenant_type: str | None = None  # anchor, inline, pad, etc.
    naics_code: str | None = None
    source: str = "unknown"  # "costar" | "placer" | "manual"


class PropertyImport(BaseModel):
    property_name: str | None = None
    address: str
    city: str | None = None
    state: str | None = None
    zip_code: str | None = None
    total_sf: int | None = None
    year_built: int | None = None
    tenants: list[TenantRecord] = []
    source: str


class TradeAreaMetrics(BaseModel):
    """Placer-style trade area data."""
    property_address: str
    property_name: str | None = None
    reporting_period: str | None = None
    visit_count_12mo: int | None = None
    unique_visitors_12mo: int | None = None
    avg_dwell_minutes: float | None = None
    home_trade_area_zip_codes: list[str] = []
    visitor_demographics: dict = {}
    cross_visit_destinations: list[str] = []
    source: str = "placer"


class VehicleTrafficRecord(BaseModel):
    """SiteUSA-style vehicle traffic data."""
    address: str
    road_name: str | None = None
    vpd: int | None = None  # vehicles per day
    direction: str | None = None
    measurement_year: int | None = None
    population_1mi: int | None = None
    population_3mi: int | None = None
    population_5mi: int | None = None
    median_hhi_3mi: float | None = None
    source: str = "siteusa"
