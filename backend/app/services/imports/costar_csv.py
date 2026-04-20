"""CoStar CSV export parser.

Supports three common CoStar export shapes:
  - Leasing (tenant-centric with lease dates and rent)
  - Tenant Roster (property-centric tenant list)
  - Property Lookup (property details with building info)

Detection is by header row. Uses fuzzy column mapping like csv_import.py.
"""

import csv
import io
import logging
from datetime import date

from app.services.imports.normalize import TenantRecord, PropertyImport

logger = logging.getLogger(__name__)

# Fuzzy column mapping — CoStar headers → normalized field names
COSTAR_COLUMN_MAP: dict[str, str] = {
    # Tenant fields
    "Tenant Name": "name",
    "Tenant": "name",
    "Company Name": "name",
    "Suite": "suite",
    "Suite/Unit": "suite",
    "Unit": "suite",
    "Size (SF)": "square_feet",
    "RBA": "square_feet",
    "Leased SF": "square_feet",
    "Occupied SF": "square_feet",
    "Space SF": "square_feet",
    "Rent ($/SF)": "rent_psf",
    "Asking Rent": "rent_psf",
    "Rent/SF": "rent_psf",
    "Direct Asking Rent": "rent_psf",
    "Lease Start": "lease_start",
    "Commencement": "lease_start",
    "Lease End": "lease_end",
    "Expiration": "lease_end",
    "Lease Expiration": "lease_end",
    "Tenant SIC": "naics_code",
    "NAICS": "naics_code",
    "SIC Code": "naics_code",
    "Tenant Type": "tenant_type",
    "Space Type": "tenant_type",
    # Property fields (prefixed with _ to distinguish)
    "Property Name": "_property_name",
    "Building Name": "_property_name",
    "Property Address": "_property_address",
    "Address": "_property_address",
    "Street Address": "_property_address",
    "City": "_city",
    "State": "_state",
    "Zip": "_zip_code",
    "Zip Code": "_zip_code",
    "Year Built": "_year_built",
    "Total SF": "_total_sf",
    "Building SF": "_total_sf",
    "Building Size": "_total_sf",
}

# Headers that signal each export shape
_LEASING_SIGNALS = {"Lease Start", "Commencement", "Lease End", "Expiration", "Lease Expiration"}
_ROSTER_SIGNALS = {"Tenant Name", "Tenant", "Suite", "Suite/Unit"}
_PROPERTY_SIGNALS = {"Year Built", "Building SF", "Total SF", "Property Type"}


def _detect_export_type(headers: list[str]) -> str:
    header_set = set(headers)
    if header_set & _LEASING_SIGNALS:
        return "leasing"
    if header_set & _ROSTER_SIGNALS:
        return "roster"
    if header_set & _PROPERTY_SIGNALS:
        return "property_lookup"
    return "unknown"


def _map_columns(headers: list[str]) -> dict[int, str]:
    """Map column index → normalized field name using fuzzy matching."""
    mapping: dict[int, str] = {}
    for i, header in enumerate(headers):
        clean = header.strip()
        if clean in COSTAR_COLUMN_MAP:
            mapping[i] = COSTAR_COLUMN_MAP[clean]
        else:
            # Case-insensitive fallback
            for key, value in COSTAR_COLUMN_MAP.items():
                if key.lower() == clean.lower():
                    mapping[i] = value
                    break
    return mapping


def _parse_date(val: str) -> date | None:
    if not val or not val.strip():
        return None
    for fmt in ("%m/%d/%Y", "%Y-%m-%d", "%m-%d-%Y", "%m/%d/%y"):
        try:
            return date.fromisoformat(val.strip()) if fmt == "%Y-%m-%d" else __import__("datetime").datetime.strptime(val.strip(), fmt).date()
        except ValueError:
            continue
    return None


def _parse_int(val: str) -> int | None:
    if not val or not val.strip():
        return None
    try:
        return int(val.strip().replace(",", "").replace(" ", ""))
    except ValueError:
        return None


def _parse_float(val: str) -> float | None:
    if not val or not val.strip():
        return None
    try:
        return float(val.strip().replace(",", "").replace("$", "").replace(" ", ""))
    except ValueError:
        return None


def parse_costar_csv(file_bytes: bytes) -> list[PropertyImport]:
    """Parse a CoStar CSV export into normalized PropertyImport objects.

    Returns a list because a single export can contain data for multiple properties.
    """
    text = file_bytes.decode("utf-8-sig")  # handle BOM
    reader = csv.reader(io.StringIO(text))

    try:
        headers = next(reader)
    except StopIteration:
        raise ValueError("Empty CSV file")

    export_type = _detect_export_type(headers)
    col_map = _map_columns(headers)

    if not col_map:
        raise ValueError(
            f"Could not map any CoStar columns. Headers found: {headers[:10]}"
        )

    logger.info("CoStar CSV detected as '%s' with %d mapped columns", export_type, len(col_map))

    # Group rows by property address
    properties: dict[str, dict] = {}  # address → {name, city, state, zip, total_sf, year_built, tenants}

    for row_num, row in enumerate(reader, start=2):
        if not any(cell.strip() for cell in row):
            continue  # skip blank rows

        record: dict = {}
        for col_idx, field_name in col_map.items():
            if col_idx < len(row):
                record[field_name] = row[col_idx].strip()

        # Extract property-level fields
        prop_address = record.get("_property_address", "")
        if not prop_address:
            prop_address = f"Unknown Property (row {row_num})"

        if prop_address not in properties:
            properties[prop_address] = {
                "name": record.get("_property_name"),
                "city": record.get("_city"),
                "state": record.get("_state"),
                "zip_code": record.get("_zip_code"),
                "total_sf": _parse_int(record.get("_total_sf", "")),
                "year_built": _parse_int(record.get("_year_built", "")),
                "tenants": [],
            }

        # Extract tenant-level fields (if present)
        tenant_name = record.get("name", "").strip()
        if tenant_name:
            tenant = TenantRecord(
                name=tenant_name,
                suite=record.get("suite"),
                square_feet=_parse_int(record.get("square_feet", "")),
                rent_psf=_parse_float(record.get("rent_psf", "")),
                lease_start=_parse_date(record.get("lease_start", "")),
                lease_end=_parse_date(record.get("lease_end", "")),
                tenant_type=record.get("tenant_type"),
                naics_code=record.get("naics_code"),
                source="costar",
            )
            properties[prop_address]["tenants"].append(tenant)

    results = []
    for address, data in properties.items():
        results.append(PropertyImport(
            property_name=data["name"],
            address=address,
            city=data["city"],
            state=data["state"],
            zip_code=data["zip_code"],
            total_sf=data["total_sf"],
            year_built=data["year_built"],
            tenants=data["tenants"],
            source="costar",
        ))

    logger.info("Parsed %d properties with %d total tenants from CoStar CSV",
                len(results), sum(len(p.tenants) for p in results))
    return results
