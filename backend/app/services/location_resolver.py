"""
Location Resolver Service

Master-owned capability that converts city/state inputs into canonical location objects
with FIPS codes, ZIP codes, and coordinates that all downstream tools can use.

This solves the problem where tools like the Census API require specific identifiers
(ZIP, FIPS codes) but users provide general locations like "Reno, NV".
"""

import re
import httpx
import logging
from dataclasses import dataclass, field
from typing import Any
from enum import Enum

from app.core.config import settings

logger = logging.getLogger(__name__)

class ResolutionMethod(str, Enum):
    """How the location was resolved."""
    CENSUS_GEOCODER = "census_geocoder"  # Full address geocoding
    CENSUS_PLACE_LOOKUP = "census_place_lookup"  # City/state to place FIPS
    GOOGLE_GEOCODING = "google_geocoding"  # Google Maps geocoding
    ZIP_LOOKUP = "zip_lookup"  # ZIP code database
    FALLBACK = "fallback"  # Used defaults/estimates


class ResolutionConfidence(str, Enum):
    """Confidence level of the resolution."""
    HIGH = "high"  # Exact match found
    MEDIUM = "medium"  # Good match with some inference
    LOW = "low"  # Best guess, may need clarification


@dataclass
class ResolvedLocation:
    """
    Canonical location object returned by the resolver.
    All tools should accept this format for consistent location handling.
    """
    # Display and identification
    display_name: str
    normalized_city: str | None = None
    state_abbrev: str | None = None
    state_name: str | None = None

    # Census FIPS codes (for Census API)
    state_fips: str | None = None
    county_fips: str | None = None
    place_fips: str | None = None
    tract: str | None = None
    county_subdivision: str | None = None

    # Coordinates (for radius searches)
    latitude: float | None = None
    longitude: float | None = None

    # ZIP codes (for ZCTA demographics)
    primary_zip: str | None = None
    zip_codes: list[str] = field(default_factory=list)

    # Metadata
    confidence: ResolutionConfidence = ResolutionConfidence.MEDIUM
    method: ResolutionMethod = ResolutionMethod.FALLBACK
    original_input: str = ""

    # Fallback flags
    used_county_fallback: bool = False
    used_zip_approximation: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "display_name": self.display_name,
            "normalized_city": self.normalized_city,
            "state_abbrev": self.state_abbrev,
            "state_name": self.state_name,
            "state_fips": self.state_fips,
            "county_fips": self.county_fips,
            "place_fips": self.place_fips,
            "tract": self.tract,
            "county_subdivision": self.county_subdivision,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "primary_zip": self.primary_zip,
            "zip_codes": self.zip_codes,
            "confidence": self.confidence.value,
            "method": self.method.value,
            "original_input": self.original_input,
            "used_county_fallback": self.used_county_fallback,
            "used_zip_approximation": self.used_zip_approximation,
        }

    def has_census_identifiers(self) -> bool:
        """Check if we have enough info for Census API calls."""
        return bool(self.state_fips and (self.place_fips or self.county_fips or self.tract))

    def has_zip(self) -> bool:
        """Check if we have ZIP code(s) for ZCTA queries."""
        return bool(self.primary_zip or self.zip_codes)

    def has_coordinates(self) -> bool:
        """Check if we have coordinates for radius searches."""
        return self.latitude is not None and self.longitude is not None


# State name to FIPS code mapping
STATE_FIPS = {
    "AL": "01", "AK": "02", "AZ": "04", "AR": "05", "CA": "06",
    "CO": "08", "CT": "09", "DE": "10", "DC": "11", "FL": "12",
    "GA": "13", "HI": "15", "ID": "16", "IL": "17", "IN": "18",
    "IA": "19", "KS": "20", "KY": "21", "LA": "22", "ME": "23",
    "MD": "24", "MA": "25", "MI": "26", "MN": "27", "MS": "28",
    "MO": "29", "MT": "30", "NE": "31", "NV": "32", "NH": "33",
    "NJ": "34", "NM": "35", "NY": "36", "NC": "37", "ND": "38",
    "OH": "39", "OK": "40", "OR": "41", "PA": "42", "RI": "44",
    "SC": "45", "SD": "46", "TN": "47", "TX": "48", "UT": "49",
    "VT": "50", "VA": "51", "WA": "53", "WV": "54", "WI": "55", "WY": "56",
}

STATE_NAMES = {
    "alabama": "AL", "alaska": "AK", "arizona": "AZ", "arkansas": "AR",
    "california": "CA", "colorado": "CO", "connecticut": "CT", "delaware": "DE",
    "district of columbia": "DC", "florida": "FL", "georgia": "GA", "hawaii": "HI",
    "idaho": "ID", "illinois": "IL", "indiana": "IN", "iowa": "IA", "kansas": "KS",
    "kentucky": "KY", "louisiana": "LA", "maine": "ME", "maryland": "MD",
    "massachusetts": "MA", "michigan": "MI", "minnesota": "MN", "mississippi": "MS",
    "missouri": "MO", "montana": "MT", "nebraska": "NE", "nevada": "NV",
    "new hampshire": "NH", "new jersey": "NJ", "new mexico": "NM", "new york": "NY",
    "north carolina": "NC", "north dakota": "ND", "ohio": "OH", "oklahoma": "OK",
    "oregon": "OR", "pennsylvania": "PA", "rhode island": "RI", "south carolina": "SC",
    "south dakota": "SD", "tennessee": "TN", "texas": "TX", "utah": "UT",
    "vermont": "VT", "virginia": "VA", "washington": "WA", "west virginia": "WV",
    "wisconsin": "WI", "wyoming": "WY",
}


def _normalize_state(state_input: str) -> str | None:
    """Normalize state input to 2-letter abbreviation."""
    state_input = state_input.strip().upper()

    # Already a valid abbreviation
    if state_input in STATE_FIPS:
        return state_input

    # Try full name
    state_lower = state_input.lower()
    if state_lower in STATE_NAMES:
        return STATE_NAMES[state_lower]

    return None


def _parse_location_input(location: str) -> tuple[str | None, str | None, str | None]:
    """
    Parse location input into components.

    Returns: (street_address, city, state_abbrev)
    """
    location = location.strip()

    # Check for ZIP code pattern
    zip_match = re.search(r'\b(\d{5})(?:-\d{4})?\b', location)
    zip_code = zip_match.group(1) if zip_match else None

    # Try to extract state
    state_abbrev = None
    city = None
    street = None

    # Pattern: "City, State" or "City, State ZIP"
    city_state_pattern = r'^(.+?),\s*([A-Za-z]{2})\s*(?:\d{5})?$'
    match = re.match(city_state_pattern, location)
    if match:
        city = match.group(1).strip()
        state_abbrev = _normalize_state(match.group(2))
        return None, city, state_abbrev

    # Pattern: "City, Full State Name"
    full_state_pattern = r'^(.+?),\s*([A-Za-z\s]+?)(?:\s+\d{5})?$'
    match = re.match(full_state_pattern, location)
    if match:
        potential_city = match.group(1).strip()
        potential_state = match.group(2).strip()
        normalized = _normalize_state(potential_state)
        if normalized:
            return None, potential_city, normalized

    # Pattern: Full address with street
    # Look for common street suffixes
    street_suffixes = ['st', 'street', 'ave', 'avenue', 'rd', 'road', 'blvd',
                       'boulevard', 'dr', 'drive', 'ln', 'lane', 'way', 'pkwy',
                       'parkway', 'ct', 'court', 'pl', 'place', 'hwy', 'highway']

    location_lower = location.lower()
    has_street = any(f' {suffix}' in location_lower or f' {suffix},' in location_lower
                     for suffix in street_suffixes)

    if has_street or re.match(r'^\d+\s+', location):
        # Likely a full address
        # Try to split on last comma to get state
        parts = location.rsplit(',', 2)
        if len(parts) >= 2:
            last_part = parts[-1].strip()
            state_zip_match = re.match(r'^([A-Za-z]{2})\s*(?:\d{5})?$', last_part)
            if state_zip_match:
                state_abbrev = _normalize_state(state_zip_match.group(1))
                city = parts[-2].strip() if len(parts) > 2 else None
                street = parts[0].strip() if len(parts) > 2 else parts[0].strip()
                return street, city, state_abbrev

    return None, location, None


async def _geocode_with_google(location: str) -> ResolvedLocation | None:
    """
    Use Google Geocoding API to resolve a location.
    Returns coordinates and address components.
    """
    if not settings.google_places_api_key:
        return None

    geocode_url = "https://maps.googleapis.com/maps/api/geocode/json"
    params = {
        "address": location,
        "key": settings.google_places_api_key,
    }

    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            response = await client.get(geocode_url, params=params)
            response.raise_for_status()
            data = response.json()

            if data.get("status") != "OK" or not data.get("results"):
                return None

            result = data["results"][0]
            geometry = result.get("geometry", {}).get("location", {})

            # Extract address components
            components = result.get("address_components", [])

            city = None
            state_abbrev = None
            state_name = None
            zip_code = None
            county = None

            for comp in components:
                types = comp.get("types", [])
                if "locality" in types:
                    city = comp.get("long_name")
                elif "administrative_area_level_1" in types:
                    state_abbrev = comp.get("short_name")
                    state_name = comp.get("long_name")
                elif "postal_code" in types:
                    zip_code = comp.get("short_name")[:5]
                elif "administrative_area_level_2" in types:
                    county = comp.get("long_name")

            if not state_abbrev:
                return None

            state_fips = STATE_FIPS.get(state_abbrev)

            return ResolvedLocation(
                display_name=result.get("formatted_address", location),
                normalized_city=city,
                state_abbrev=state_abbrev,
                state_name=state_name,
                state_fips=state_fips,
                latitude=geometry.get("lat"),
                longitude=geometry.get("lng"),
                primary_zip=zip_code,
                zip_codes=[zip_code] if zip_code else [],
                confidence=ResolutionConfidence.HIGH if zip_code else ResolutionConfidence.MEDIUM,
                method=ResolutionMethod.GOOGLE_GEOCODING,
                original_input=location,
            )

        except Exception:
            logger.exception("[location_resolver] Google geocoding error")
            return None


async def _geocode_with_census(location: str) -> ResolvedLocation | None:
    """
    Use Census Bureau Geocoder to resolve an address.
    Works best with full street addresses.
    """
    geocoder_url = "https://geocoding.geo.census.gov/geocoder/geographies/onelineaddress"
    params = {
        "address": location,
        "benchmark": "Public_AR_Current",
        "vintage": "Current_Current",
        "format": "json",
        "layers": "all",
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.get(geocoder_url, params=params)
            response.raise_for_status()
            data = response.json()

            matches = data.get("result", {}).get("addressMatches", [])
            if not matches:
                return None

            match = matches[0]
            coords = match.get("coordinates", {})
            geographies = match.get("geographies", {})

            # Extract tract info
            tracts = geographies.get("Census Tracts", [])
            if not tracts:
                return None

            tract_info = tracts[0]

            # Extract other geographies
            subdivisions = geographies.get("County Subdivisions", [])
            places = geographies.get("Incorporated Places", [])

            subdivision = subdivisions[0].get("COUSUB") if subdivisions else None
            place_fips = places[0].get("PLACE") if places else None
            place_name = places[0].get("NAME") if places else None

            return ResolvedLocation(
                display_name=match.get("matchedAddress", location),
                normalized_city=place_name,
                state_fips=tract_info.get("STATE", ""),
                county_fips=tract_info.get("COUNTY", ""),
                place_fips=place_fips,
                tract=tract_info.get("TRACT", ""),
                county_subdivision=subdivision,
                latitude=coords.get("y"),
                longitude=coords.get("x"),
                confidence=ResolutionConfidence.HIGH,
                method=ResolutionMethod.CENSUS_GEOCODER,
                original_input=location,
            )

        except Exception:
            logger.exception("[location_resolver] Census geocoding error")
            return None


async def _lookup_place_fips(city: str, state_abbrev: str) -> dict | None:
    """
    Look up Census Place FIPS code for a city/state combination.
    Uses Census API to search for incorporated places.
    """
    state_fips = STATE_FIPS.get(state_abbrev)
    if not state_fips:
        return None

    # Census API for places
    url = f"https://api.census.gov/data/2022/acs/acs5?get=NAME,B01003_001E&for=place:*&in=state:{state_fips}"
    if settings.census_api_key:
        url += f"&key={settings.census_api_key}"

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.get(url)
            response.raise_for_status()
            data = response.json()

            if len(data) < 2:
                return None

            # Search for matching city
            city_lower = city.lower().strip()
            city_variations = [
                city_lower,
                f"{city_lower} city",
                f"{city_lower} town",
                f"city of {city_lower}",
            ]

            for row in data[1:]:
                name = row[0].lower()
                population = int(row[1]) if row[1] else 0
                place_code = row[3]

                # Check if any variation matches
                for variation in city_variations:
                    if variation in name or name.startswith(city_lower):
                        return {
                            "name": row[0],
                            "place_fips": place_code,
                            "state_fips": state_fips,
                            "population": population,
                        }

            return None

        except Exception:
            logger.exception("[location_resolver] Place FIPS lookup error")
            return None


async def _lookup_zip_for_city(city: str, state_abbrev: str) -> list[str]:
    """
    Look up representative ZIP codes for a city using Google Geocoding.
    """
    if not settings.google_places_api_key:
        return []

    # Search for the city center
    query = f"{city}, {state_abbrev}, USA"
    resolved = await _geocode_with_google(query)

    if resolved and resolved.primary_zip:
        return [resolved.primary_zip]

    return []


async def resolve_location(input_string: str) -> ResolvedLocation:
    """
    Master location resolver function.

    Converts any location input (city/state, address, ZIP, etc.) into a canonical
    ResolvedLocation object that tools can use.

    Resolution strategy:
    1. Parse input to identify components (street, city, state, ZIP)
    2. If full address, try Census Geocoder first (best FIPS data)
    3. If city/state only, try place FIPS lookup
    4. Fall back to Google Geocoding for coordinates and ZIP
    5. If all else fails, return partial data with low confidence

    Args:
        input_string: Location string from user (e.g., "Reno, NV", "123 Main St, Boston, MA")

    Returns:
        ResolvedLocation with available identifiers and confidence level
    """
    input_string = input_string.strip()
    if not input_string:
        return ResolvedLocation(
            display_name="Unknown",
            confidence=ResolutionConfidence.LOW,
            method=ResolutionMethod.FALLBACK,
            original_input=input_string,
        )

    # Parse the input
    street, city, state_abbrev = _parse_location_input(input_string)

    # Check for ZIP code in input
    zip_match = re.search(r'\b(\d{5})\b', input_string)
    input_zip = zip_match.group(1) if zip_match else None

    logger.debug("[location_resolver] Parsed input")

    # Strategy 1: Full address - try Census Geocoder
    if street and state_abbrev:
        result = await _geocode_with_census(input_string)
        if result:
            if input_zip:
                result.primary_zip = input_zip
                result.zip_codes = [input_zip]
            logger.debug("[location_resolver] Census geocoder success")
            return result

    # Strategy 2: City/State - try place FIPS lookup
    if city and state_abbrev:
        place_info = await _lookup_place_fips(city, state_abbrev)
        if place_info:
            # Get coordinates via Google
            google_result = await _geocode_with_google(f"{city}, {state_abbrev}")

            zip_codes = []
            if google_result and google_result.primary_zip:
                zip_codes = [google_result.primary_zip]
            elif input_zip:
                zip_codes = [input_zip]

            return ResolvedLocation(
                display_name=f"{place_info['name']}, {state_abbrev}",
                normalized_city=city.title(),
                state_abbrev=state_abbrev,
                state_fips=place_info["state_fips"],
                place_fips=place_info["place_fips"],
                latitude=google_result.latitude if google_result else None,
                longitude=google_result.longitude if google_result else None,
                primary_zip=zip_codes[0] if zip_codes else None,
                zip_codes=zip_codes,
                confidence=ResolutionConfidence.HIGH,
                method=ResolutionMethod.CENSUS_PLACE_LOOKUP,
                original_input=input_string,
            )

    # Strategy 3: Use Google Geocoding as fallback
    google_result = await _geocode_with_google(input_string)
    if google_result:
        # Try to also get place FIPS if we have city/state
        if google_result.normalized_city and google_result.state_abbrev:
            place_info = await _lookup_place_fips(
                google_result.normalized_city,
                google_result.state_abbrev
            )
            if place_info:
                google_result.place_fips = place_info["place_fips"]
                google_result.confidence = ResolutionConfidence.HIGH

        logger.debug("[location_resolver] Google geocoding success")
        return google_result

    # Strategy 4: ZIP code only
    if input_zip:
        return ResolvedLocation(
            display_name=f"ZIP {input_zip}",
            primary_zip=input_zip,
            zip_codes=[input_zip],
            confidence=ResolutionConfidence.MEDIUM,
            method=ResolutionMethod.ZIP_LOOKUP,
            original_input=input_string,
            used_zip_approximation=True,
        )

    # Strategy 5: Partial resolution - at least get state
    if state_abbrev:
        state_fips = STATE_FIPS.get(state_abbrev)
        return ResolvedLocation(
            display_name=input_string,
            normalized_city=city,
            state_abbrev=state_abbrev,
            state_fips=state_fips,
            confidence=ResolutionConfidence.LOW,
            method=ResolutionMethod.FALLBACK,
            original_input=input_string,
        )

    # Last resort: return minimal info
    return ResolvedLocation(
        display_name=input_string,
        confidence=ResolutionConfidence.LOW,
        method=ResolutionMethod.FALLBACK,
        original_input=input_string,
    )


async def get_representative_zip_for_location(location: ResolvedLocation) -> str | None:
    """
    Get a representative ZIP code for a resolved location.
    Used when a tool requires ZIP but we only have city/state.
    """
    if location.primary_zip:
        return location.primary_zip

    if location.zip_codes:
        return location.zip_codes[0]

    # Try to look up ZIP if we have city/state
    if location.normalized_city and location.state_abbrev:
        zips = await _lookup_zip_for_city(location.normalized_city, location.state_abbrev)
        if zips:
            return zips[0]

    return None
