"""
CSV Import Service

Handles CSV imports for Airtable migration, mapping columns to Property fields
and handling duplicate detection by address.
"""

import csv
import io
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.models.deal import Property

logger = logging.getLogger(__name__)

# Map common Airtable column names to Property model field names
AIRTABLE_COLUMN_MAP: dict[str, str] = {
    # Name / address fields
    "Name": "name",
    "Property Name": "name",
    "property_name": "name",
    "Address": "address",
    "Street Address": "address",
    "Street": "address",
    "City": "city",
    "State": "state",
    "Zip": "zip_code",
    "Zip Code": "zip_code",
    "ZIP": "zip_code",
    "Zipcode": "zip_code",
    "Postal Code": "zip_code",
    # Location
    "Latitude": "latitude",
    "Lat": "latitude",
    "Longitude": "longitude",
    "Lng": "longitude",
    "Lon": "longitude",
    # Property info
    "Property Type": "property_type",
    "Type": "property_type",
    "Total SF": "total_sf",
    "Total Square Feet": "total_sf",
    "GLA": "total_sf",
    "Building Size": "total_sf",
    "Available SF": "available_sf",
    "Available Square Feet": "available_sf",
    # Market classification
    "Market Region": "market_region",
    "Region": "market_region",
    "Metro Area": "metro_area",
    "Metro": "metro_area",
    "Product Type": "product_type",
    # Intersection / traffic
    "Intersection Quality": "intersection_quality",
    "Traffic Count": "traffic_count_vpd",
    "VPD": "traffic_count_vpd",
    "Traffic Count VPD": "traffic_count_vpd",
    # Demographics
    "Population 1mi": "population_1mi",
    "Pop 1 Mile": "population_1mi",
    "Population 3mi": "population_3mi",
    "Pop 3 Mile": "population_3mi",
    "Population 5mi": "population_5mi",
    "Pop 5 Mile": "population_5mi",
    "Median HHI 3mi": "median_hhi_3mi",
    "Median HHI": "median_hhi_3mi",
    "Median Household Income": "median_hhi_3mi",
    # Ownership / zoning
    "Owner Name": "owner_name",
    "Owner": "owner_name",
    "Owner Entity": "owner_entity",
    "Entity": "owner_entity",
    "Zoning Code": "zoning_code",
    "Zoning": "zoning_code",
    "Zoning Description": "zoning_description",
    # Pricing
    "Asking Price": "asking_price",
    "Price": "asking_price",
    "Cap Rate": "cap_rate",
    "Price PSF": "price_psf",
    "NOI": "noi",
    # Broker contact
    "Broker Name": "broker_name",
    "Broker": "broker_name",
    "Broker Company": "broker_company",
    "Brokerage": "broker_company",
    "Broker Phone": "broker_phone",
    "Broker Email": "broker_email",
    # Source
    "Source Type": "source_type",
    "Source": "source_type",
    "Source URL": "source_url",
    "URL": "source_url",
    # Notes
    "Notes": "notes",
    "Comments": "notes",
}

# Property fields that should be parsed as integers
INT_FIELDS = {
    "total_sf",
    "available_sf",
    "traffic_count_vpd",
    "population_1mi",
    "population_3mi",
    "population_5mi",
}

# Property fields that should be parsed as floats
FLOAT_FIELDS = {
    "latitude",
    "longitude",
    "median_hhi_3mi",
    "asking_price",
    "cap_rate",
    "price_psf",
    "noi",
}


@dataclass
class ImportResult:
    """Result of a CSV import operation."""

    total_rows: int = 0
    imported: int = 0
    skipped: int = 0
    errors: list[str] = field(default_factory=list)


def _auto_detect_columns(
    headers: list[str],
    custom_mapping: dict[str, str] | None = None,
) -> dict[str, str]:
    """
    Auto-detect column mapping from CSV headers.

    First checks the custom mapping, then falls back to AIRTABLE_COLUMN_MAP.
    Uses case-insensitive matching with stripped whitespace.

    Args:
        headers: List of CSV column headers.
        custom_mapping: Optional custom column mapping overrides.

    Returns:
        Dict mapping CSV column name -> Property field name.
    """
    resolved: dict[str, str] = {}
    custom = custom_mapping or {}

    for header in headers:
        stripped = header.strip()

        # Check custom mapping first
        if stripped in custom:
            resolved[header] = custom[stripped]
            continue

        # Check Airtable map (exact match)
        if stripped in AIRTABLE_COLUMN_MAP:
            resolved[header] = AIRTABLE_COLUMN_MAP[stripped]
            continue

        # Case-insensitive fallback
        lower = stripped.lower()
        for airtable_col, field_name in AIRTABLE_COLUMN_MAP.items():
            if airtable_col.lower() == lower:
                resolved[header] = field_name
                break

    return resolved


def _parse_value(value: str, field_name: str) -> Any:
    """
    Parse a CSV string value into the appropriate Python type for the field.

    Args:
        value: Raw string value from CSV.
        field_name: Target Property field name.

    Returns:
        Parsed value, or None if parsing fails or value is empty.
    """
    if not value or not value.strip():
        return None

    cleaned = value.strip()

    if field_name in INT_FIELDS:
        try:
            # Remove commas and dollar signs
            cleaned = cleaned.replace(",", "").replace("$", "").replace(" ", "")
            return int(float(cleaned))
        except (ValueError, TypeError):
            return None

    if field_name in FLOAT_FIELDS:
        try:
            cleaned = cleaned.replace(",", "").replace("$", "").replace("%", "").replace(" ", "")
            return float(cleaned)
        except (ValueError, TypeError):
            return None

    return cleaned


async def import_properties_from_csv(
    file_content: bytes,
    user_id: str,
    db: AsyncSession,
    column_mapping: dict[str, str] | None = None,
) -> ImportResult:
    """
    Parse a CSV file and create Property records in the database.

    Auto-detects column mapping from headers using AIRTABLE_COLUMN_MAP,
    with optional custom overrides. Handles duplicates by checking for
    existing properties with the same address for the user.

    Args:
        file_content: Raw bytes of the CSV file.
        user_id: The user ID to associate properties with.
        db: Async database session.
        column_mapping: Optional dict mapping CSV column names to
                        Property field names. Overrides auto-detection.

    Returns:
        ImportResult with counts of total, imported, skipped, and errors.
    """
    result = ImportResult()

    # Decode CSV content
    try:
        text = file_content.decode("utf-8-sig")
    except UnicodeDecodeError:
        try:
            text = file_content.decode("latin-1")
        except UnicodeDecodeError:
            result.errors.append("Could not decode CSV file. Expected UTF-8 or Latin-1 encoding.")
            return result

    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        result.errors.append("CSV file has no headers.")
        return result

    # Auto-detect column mapping
    col_map = _auto_detect_columns(list(reader.fieldnames), column_mapping)
    mapped_fields = set(col_map.values())

    logger.info(
        "[csv_import] Detected %d column mappings: %s",
        len(col_map),
        {k: v for k, v in col_map.items()},
    )

    # Validate required fields
    required = {"name", "address", "city", "state", "zip_code"}
    missing_required = required - mapped_fields
    if missing_required:
        result.errors.append(
            f"Missing required column mappings: {', '.join(sorted(missing_required))}. "
            f"Detected columns: {', '.join(reader.fieldnames)}"
        )
        return result

    # Fetch existing addresses for duplicate detection
    existing_query = await db.execute(
        select(Property.address).where(Property.user_id == user_id)
    )
    existing_addresses = {
        addr.lower().strip()
        for (addr,) in existing_query.all()
        if addr
    }

    rows = list(reader)
    result.total_rows = len(rows)

    for row_num, row in enumerate(rows, start=2):  # Start at 2 to account for header row
        try:
            # Map CSV columns to Property fields
            property_data: dict[str, Any] = {}
            for csv_col, field_name in col_map.items():
                raw_value = row.get(csv_col, "")
                parsed = _parse_value(raw_value, field_name)
                if parsed is not None:
                    property_data[field_name] = parsed

            # Validate required fields are present
            if not property_data.get("address"):
                result.errors.append(f"Row {row_num}: Missing address, skipped.")
                result.skipped += 1
                continue

            if not property_data.get("name"):
                # Use address as name fallback
                property_data["name"] = property_data["address"]

            for field_name in ("city", "state", "zip_code"):
                if not property_data.get(field_name):
                    property_data[field_name] = "(unknown)"

            # Check for duplicates by address
            address_key = property_data["address"].lower().strip()
            if address_key in existing_addresses:
                logger.debug(
                    "[csv_import] Row %d: Duplicate address '%s', skipped",
                    row_num,
                    property_data["address"],
                )
                result.skipped += 1
                continue

            # Create Property record
            new_property = Property(
                id=str(uuid.uuid4()),
                user_id=user_id,
                source_type="csv_import",
                **property_data,
            )
            db.add(new_property)
            existing_addresses.add(address_key)
            result.imported += 1

        except Exception as e:
            error_msg = f"Row {row_num}: {e}"
            logger.error("[csv_import] %s", error_msg)
            result.errors.append(error_msg)

    # Commit all records
    if result.imported > 0:
        try:
            await db.commit()
            logger.info(
                "[csv_import] Import complete: %d imported, %d skipped, %d errors out of %d total",
                result.imported,
                result.skipped,
                len(result.errors),
                result.total_rows,
            )
        except Exception as e:
            await db.rollback()
            result.errors.append(f"Database commit error: {e}")
            result.imported = 0
            logger.error("[csv_import] Commit failed: %s", e)

    return result
