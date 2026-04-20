"""SiteUSA CSV export parser.

SiteUSA exports contain vehicle traffic counts (VPD), demographics, and
location data. Follows the same fuzzy column mapping pattern as costar_csv.py.
"""

import csv
import io
import logging

from app.services.imports.normalize import VehicleTrafficRecord

logger = logging.getLogger(__name__)

SITEUSA_COLUMN_MAP: dict[str, str] = {
    # Address fields
    "Address": "address",
    "Street Address": "address",
    "Location": "address",
    "Site Address": "address",
    # Road / traffic
    "Road Name": "road_name",
    "Street Name": "road_name",
    "Nearest Road": "road_name",
    "VPD": "vpd",
    "Traffic Count": "vpd",
    "Vehicles Per Day": "vpd",
    "Traffic Count VPD": "vpd",
    "AADT": "vpd",
    "Direction": "direction",
    "Traffic Direction": "direction",
    "Year": "measurement_year",
    "Count Year": "measurement_year",
    # Demographics
    "Population 1mi": "population_1mi",
    "Pop 1 Mile": "population_1mi",
    "1 Mile Pop": "population_1mi",
    "Population 3mi": "population_3mi",
    "Pop 3 Mile": "population_3mi",
    "3 Mile Pop": "population_3mi",
    "Population 5mi": "population_5mi",
    "Pop 5 Mile": "population_5mi",
    "5 Mile Pop": "population_5mi",
    "Median HHI": "median_hhi_3mi",
    "Median HHI 3mi": "median_hhi_3mi",
    "Median Household Income": "median_hhi_3mi",
    "HHI": "median_hhi_3mi",
}


def _map_columns(headers: list[str]) -> dict[int, str]:
    mapping: dict[int, str] = {}
    for i, header in enumerate(headers):
        clean = header.strip()
        if clean in SITEUSA_COLUMN_MAP:
            mapping[i] = SITEUSA_COLUMN_MAP[clean]
        else:
            for key, value in SITEUSA_COLUMN_MAP.items():
                if key.lower() == clean.lower():
                    mapping[i] = value
                    break
    return mapping


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


def parse_siteusa_csv(file_bytes: bytes) -> list[VehicleTrafficRecord]:
    """Parse a SiteUSA CSV export into VehicleTrafficRecord objects."""
    text = file_bytes.decode("utf-8-sig")
    reader = csv.reader(io.StringIO(text))

    try:
        headers = next(reader)
    except StopIteration:
        raise ValueError("Empty CSV file")

    col_map = _map_columns(headers)

    if not col_map:
        raise ValueError(
            f"Could not map any SiteUSA columns. Headers found: {headers[:10]}"
        )

    # Ensure we have at least an address column
    has_address = any(v == "address" for v in col_map.values())
    if not has_address:
        raise ValueError("SiteUSA CSV must have an address column")

    logger.info("SiteUSA CSV: %d mapped columns", len(col_map))

    records = []
    for row in reader:
        if not any(cell.strip() for cell in row):
            continue

        data: dict = {}
        for col_idx, field_name in col_map.items():
            if col_idx < len(row):
                data[field_name] = row[col_idx].strip()

        address = data.get("address", "").strip()
        if not address:
            continue

        records.append(VehicleTrafficRecord(
            address=address,
            road_name=data.get("road_name"),
            vpd=_parse_int(data.get("vpd", "")),
            direction=data.get("direction"),
            measurement_year=_parse_int(data.get("measurement_year", "")),
            population_1mi=_parse_int(data.get("population_1mi", "")),
            population_3mi=_parse_int(data.get("population_3mi", "")),
            population_5mi=_parse_int(data.get("population_5mi", "")),
            median_hhi_3mi=_parse_float(data.get("median_hhi_3mi", "")),
            source="siteusa",
        ))

    logger.info("Parsed %d traffic records from SiteUSA CSV", len(records))
    return records
