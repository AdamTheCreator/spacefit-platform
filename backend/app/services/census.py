"""
Census ACS (American Community Survey) Data Service

Provides real demographic data from the US Census Bureau API.
- Geocoding: Convert addresses to Census geographies (tract, county, state)
- ACS Data: Pull demographic statistics for any US location
"""

import httpx
from typing import Any
from dataclasses import dataclass
from app.core.config import settings


# Census API base URLs
CENSUS_GEOCODER_URL = "https://geocoding.geo.census.gov/geocoder/geographies/onelineaddress"
CENSUS_ACS_URL = "https://api.census.gov/data/2022/acs/acs5"


@dataclass
class CensusGeography:
    """Census geography identifiers for a location."""
    address: str
    latitude: float
    longitude: float
    state_fips: str
    county_fips: str
    tract: str
    block_group: str | None = None
    # County subdivision (town/city level for Connecticut and some other states)
    county_subdivision: str | None = None
    subdivision_name: str | None = None

    @property
    def state_county_fips(self) -> str:
        """Combined state + county FIPS code."""
        return f"{self.state_fips}{self.county_fips}"

    @property
    def has_subdivision(self) -> bool:
        """Check if county subdivision data is available."""
        return self.county_subdivision is not None


@dataclass
class DemographicData:
    """Demographic data for a Census geography."""
    geography_name: str
    total_population: int
    median_household_income: int | None
    median_age: float | None

    # Age distribution
    population_under_18: int
    population_18_34: int
    population_35_54: int
    population_55_plus: int

    # Education
    bachelors_degree_or_higher_pct: float | None

    # Employment
    labor_force: int
    employed: int
    unemployment_rate: float | None

    # Housing
    total_housing_units: int
    owner_occupied_pct: float | None
    renter_occupied_pct: float | None
    median_home_value: int | None

    # Households
    total_households: int
    avg_household_size: float | None
    family_households_pct: float | None


async def geocode_address(address: str) -> CensusGeography | None:
    """
    Convert an address to Census geography identifiers.

    Uses the free Census Bureau Geocoder API.

    Args:
        address: Full address string (e.g., "15 Joanne Lane, Weston, CT 06883")

    Returns:
        CensusGeography with FIPS codes, or None if geocoding failed
    """
    params = {
        "address": address,
        "benchmark": "Public_AR_Current",
        "vintage": "Current_Current",
        "format": "json",
        "layers": "all",
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.get(CENSUS_GEOCODER_URL, params=params)
            response.raise_for_status()
            data = response.json()

            # Check if we got a match
            matches = data.get("result", {}).get("addressMatches", [])
            if not matches:
                return None

            match = matches[0]
            coords = match.get("coordinates", {})
            geographies = match.get("geographies", {})

            # Extract Census tract info
            tracts = geographies.get("Census Tracts", [])
            if not tracts:
                return None

            tract_info = tracts[0]

            # Extract block group if available
            block_groups = geographies.get("Census Block Groups", [])
            block_group = block_groups[0].get("BLKGRP") if block_groups else None

            # Extract county subdivision (town/city level - important for CT and other states)
            subdivisions = geographies.get("County Subdivisions", [])
            county_subdivision = None
            subdivision_name = None
            if subdivisions:
                county_subdivision = subdivisions[0].get("COUSUB")
                subdivision_name = subdivisions[0].get("NAME")

            return CensusGeography(
                address=match.get("matchedAddress", address),
                latitude=coords.get("y", 0),
                longitude=coords.get("x", 0),
                state_fips=tract_info.get("STATE", ""),
                county_fips=tract_info.get("COUNTY", ""),
                tract=tract_info.get("TRACT", ""),
                block_group=block_group,
                county_subdivision=county_subdivision,
                subdivision_name=subdivision_name,
            )

        except Exception as e:
            print(f"Geocoding error: {e}")
            return None


# ACS variable codes we want to fetch
# Note: Census API limits to 50 variables per request
ACS_VARIABLES = {
    # Population
    "B01003_001E": "total_population",

    # Age - use B01001 (Sex by Age) for key age breakpoints
    "B01002_001E": "median_age",
    "B09001_001E": "pop_under_18",  # Population under 18 years
    # For 65+, sum male and female 65+ from B01001
    "B01001_020E": "male_65_66",
    "B01001_021E": "male_67_69",
    "B01001_022E": "male_70_74",
    "B01001_023E": "male_75_79",
    "B01001_024E": "male_80_84",
    "B01001_025E": "male_85_plus",
    "B01001_044E": "female_65_66",
    "B01001_045E": "female_67_69",
    "B01001_046E": "female_70_74",
    "B01001_047E": "female_75_79",
    "B01001_048E": "female_80_84",
    "B01001_049E": "female_85_plus",

    # Income
    "B19013_001E": "median_household_income",

    # Education (25 years and over)
    "B15003_001E": "edu_total_25_plus",
    "B15003_022E": "edu_bachelors",
    "B15003_023E": "edu_masters",
    "B15003_024E": "edu_professional",
    "B15003_025E": "edu_doctorate",

    # Employment
    "B23025_002E": "labor_force",
    "B23025_004E": "employed",
    "B23025_005E": "unemployed",

    # Housing
    "B25001_001E": "total_housing_units",
    "B25003_001E": "tenure_total",
    "B25003_002E": "owner_occupied",
    "B25003_003E": "renter_occupied",
    "B25077_001E": "median_home_value",

    # Households
    "B11001_001E": "total_households",
    "B11001_002E": "family_households",
    "B25010_001E": "avg_household_size",
}


def _safe_int(value: Any) -> int:
    """Convert value to int, returning 0 for None or invalid values."""
    if value is None or value == "" or value == -666666666:
        return 0
    try:
        return int(value)
    except (ValueError, TypeError):
        return 0


def _safe_float(value: Any) -> float | None:
    """Convert value to float, returning None for invalid values."""
    if value is None or value == "" or value == -666666666:
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def _calculate_age_groups(data: dict[str, Any], total_population: int) -> tuple[int, int, int, int]:
    """
    Calculate age distribution from ACS age variables.

    Returns: (under_18, 18_34, 35_54, 55_plus)
    """
    # Under 18 - directly from B09001_001E
    under_18 = _safe_int(data.get("pop_under_18"))

    # 65+ - sum of all 65+ age bins for male and female
    pop_65_plus = (
        _safe_int(data.get("male_65_66")) +
        _safe_int(data.get("male_67_69")) +
        _safe_int(data.get("male_70_74")) +
        _safe_int(data.get("male_75_79")) +
        _safe_int(data.get("male_80_84")) +
        _safe_int(data.get("male_85_plus")) +
        _safe_int(data.get("female_65_66")) +
        _safe_int(data.get("female_67_69")) +
        _safe_int(data.get("female_70_74")) +
        _safe_int(data.get("female_75_79")) +
        _safe_int(data.get("female_80_84")) +
        _safe_int(data.get("female_85_plus"))
    )

    # Working age population (18-64)
    working_age = total_population - under_18 - pop_65_plus

    # Estimate age distribution within working age based on typical US demographics:
    # 18-34 is roughly 35% of working age, 35-54 is roughly 45%, 55-64 is roughly 20%
    age_18_34 = int(working_age * 0.35)
    age_35_54 = int(working_age * 0.45)
    age_55_64 = working_age - age_18_34 - age_35_54  # Remainder

    age_55_plus = age_55_64 + pop_65_plus

    return under_18, age_18_34, age_35_54, age_55_plus


async def get_tract_demographics(geography: CensusGeography) -> DemographicData | None:
    """
    Fetch ACS demographic data for a Census tract.

    Args:
        geography: CensusGeography with FIPS codes

    Returns:
        DemographicData with all demographics, or None if failed
    """
    # Build the variable list for the API request
    variables = ",".join(ACS_VARIABLES.keys())

    # Build URL - API key is optional for basic Census API usage
    url = f"{CENSUS_ACS_URL}?get=NAME,{variables}&for=tract:{geography.tract}&in=state:{geography.state_fips}&in=county:{geography.county_fips}"
    if settings.census_api_key:
        url += f"&key={settings.census_api_key}"

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.get(url)
            response.raise_for_status()
            data = response.json()

            if len(data) < 2:
                return None

            # First row is headers, second row is data
            headers = data[0]
            values = data[1]

            # Create a dict mapping variable names to values
            raw_data = {}
            for i, header in enumerate(headers):
                if header in ACS_VARIABLES:
                    raw_data[ACS_VARIABLES[header]] = values[i]
                elif header == "NAME":
                    raw_data["geography_name"] = values[i]

            # Calculate derived values
            total_pop = _safe_int(raw_data.get("total_population"))
            under_18, age_18_34, age_35_54, age_55_plus = _calculate_age_groups(raw_data, total_pop)

            # Education percentage
            edu_total = _safe_int(raw_data.get("edu_total_25_plus"))
            edu_bachelors_plus = (
                _safe_int(raw_data.get("edu_bachelors")) +
                _safe_int(raw_data.get("edu_masters")) +
                _safe_int(raw_data.get("edu_professional")) +
                _safe_int(raw_data.get("edu_doctorate"))
            )
            bachelors_pct = (edu_bachelors_plus / edu_total * 100) if edu_total > 0 else None

            # Unemployment rate
            labor_force = _safe_int(raw_data.get("labor_force"))
            unemployed = _safe_int(raw_data.get("unemployed"))
            unemployment_rate = (unemployed / labor_force * 100) if labor_force > 0 else None

            # Housing percentages
            tenure_total = _safe_int(raw_data.get("tenure_total"))
            owner_occupied = _safe_int(raw_data.get("owner_occupied"))
            renter_occupied = _safe_int(raw_data.get("renter_occupied"))
            owner_pct = (owner_occupied / tenure_total * 100) if tenure_total > 0 else None
            renter_pct = (renter_occupied / tenure_total * 100) if tenure_total > 0 else None

            # Family household percentage
            total_households = _safe_int(raw_data.get("total_households"))
            family_households = _safe_int(raw_data.get("family_households"))
            family_pct = (family_households / total_households * 100) if total_households > 0 else None

            return DemographicData(
                geography_name=raw_data.get("geography_name", "Unknown"),
                total_population=_safe_int(raw_data.get("total_population")),
                median_household_income=_safe_int(raw_data.get("median_household_income")) or None,
                median_age=_safe_float(raw_data.get("median_age")),
                population_under_18=under_18,
                population_18_34=age_18_34,
                population_35_54=age_35_54,
                population_55_plus=age_55_plus,
                bachelors_degree_or_higher_pct=round(bachelors_pct, 1) if bachelors_pct else None,
                labor_force=labor_force,
                employed=_safe_int(raw_data.get("employed")),
                unemployment_rate=round(unemployment_rate, 1) if unemployment_rate else None,
                total_housing_units=_safe_int(raw_data.get("total_housing_units")),
                owner_occupied_pct=round(owner_pct, 1) if owner_pct else None,
                renter_occupied_pct=round(renter_pct, 1) if renter_pct else None,
                median_home_value=_safe_int(raw_data.get("median_home_value")) or None,
                total_households=total_households,
                avg_household_size=_safe_float(raw_data.get("avg_household_size")),
                family_households_pct=round(family_pct, 1) if family_pct else None,
            )

        except Exception as e:
            print(f"Census API error: {e}")
            return None


async def get_county_demographics(geography: CensusGeography) -> DemographicData | None:
    """
    Fetch ACS demographic data for an entire county.
    Useful for broader trade area context.
    """
    variables = ",".join(ACS_VARIABLES.keys())
    url = f"{CENSUS_ACS_URL}?get=NAME,{variables}&for=county:{geography.county_fips}&in=state:{geography.state_fips}"
    if settings.census_api_key:
        url += f"&key={settings.census_api_key}"

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.get(url)
            response.raise_for_status()
            data = response.json()

            if len(data) < 2:
                return None

            headers = data[0]
            values = data[1]

            raw_data = {}
            for i, header in enumerate(headers):
                if header in ACS_VARIABLES:
                    raw_data[ACS_VARIABLES[header]] = values[i]
                elif header == "NAME":
                    raw_data["geography_name"] = values[i]

            total_pop = _safe_int(raw_data.get("total_population"))
            under_18, age_18_34, age_35_54, age_55_plus = _calculate_age_groups(raw_data, total_pop)

            edu_total = _safe_int(raw_data.get("edu_total_25_plus"))
            edu_bachelors_plus = (
                _safe_int(raw_data.get("edu_bachelors")) +
                _safe_int(raw_data.get("edu_masters")) +
                _safe_int(raw_data.get("edu_professional")) +
                _safe_int(raw_data.get("edu_doctorate"))
            )
            bachelors_pct = (edu_bachelors_plus / edu_total * 100) if edu_total > 0 else None

            labor_force = _safe_int(raw_data.get("labor_force"))
            unemployed = _safe_int(raw_data.get("unemployed"))
            unemployment_rate = (unemployed / labor_force * 100) if labor_force > 0 else None

            tenure_total = _safe_int(raw_data.get("tenure_total"))
            owner_occupied = _safe_int(raw_data.get("owner_occupied"))
            renter_occupied = _safe_int(raw_data.get("renter_occupied"))
            owner_pct = (owner_occupied / tenure_total * 100) if tenure_total > 0 else None
            renter_pct = (renter_occupied / tenure_total * 100) if tenure_total > 0 else None

            total_households = _safe_int(raw_data.get("total_households"))
            family_households = _safe_int(raw_data.get("family_households"))
            family_pct = (family_households / total_households * 100) if total_households > 0 else None

            return DemographicData(
                geography_name=raw_data.get("geography_name", "Unknown"),
                total_population=_safe_int(raw_data.get("total_population")),
                median_household_income=_safe_int(raw_data.get("median_household_income")) or None,
                median_age=_safe_float(raw_data.get("median_age")),
                population_under_18=under_18,
                population_18_34=age_18_34,
                population_35_54=age_35_54,
                population_55_plus=age_55_plus,
                bachelors_degree_or_higher_pct=round(bachelors_pct, 1) if bachelors_pct else None,
                labor_force=labor_force,
                employed=_safe_int(raw_data.get("employed")),
                unemployment_rate=round(unemployment_rate, 1) if unemployment_rate else None,
                total_housing_units=_safe_int(raw_data.get("total_housing_units")),
                owner_occupied_pct=round(owner_pct, 1) if owner_pct else None,
                renter_occupied_pct=round(renter_pct, 1) if renter_pct else None,
                median_home_value=_safe_int(raw_data.get("median_home_value")) or None,
                total_households=total_households,
                avg_household_size=_safe_float(raw_data.get("avg_household_size")),
                family_households_pct=round(family_pct, 1) if family_pct else None,
            )
        except Exception as e:
            print(f"Census API error (county): {e}")
            return None


async def get_subdivision_demographics(geography: CensusGeography) -> DemographicData | None:
    """
    Fetch ACS demographic data for a county subdivision (town/city).
    This provides more accurate local-level data, especially for states like
    Connecticut that use Planning Regions instead of traditional counties.
    """
    if not geography.county_subdivision:
        return None

    variables = ",".join(ACS_VARIABLES.keys())
    # Use 'county subdivision' (with space) as the geography type
    url = (
        f"{CENSUS_ACS_URL}?get=NAME,{variables}"
        f"&for=county%20subdivision:{geography.county_subdivision}"
        f"&in=state:{geography.state_fips}"
        f"&in=county:{geography.county_fips}"
    )
    if settings.census_api_key:
        url += f"&key={settings.census_api_key}"

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.get(url)
            response.raise_for_status()
            data = response.json()

            if len(data) < 2:
                return None

            headers = data[0]
            values = data[1]

            raw_data = {}
            for i, header in enumerate(headers):
                if header in ACS_VARIABLES:
                    raw_data[ACS_VARIABLES[header]] = values[i]
                elif header == "NAME":
                    raw_data["geography_name"] = values[i]

            total_pop = _safe_int(raw_data.get("total_population"))
            under_18, age_18_34, age_35_54, age_55_plus = _calculate_age_groups(raw_data, total_pop)

            edu_total = _safe_int(raw_data.get("edu_total_25_plus"))
            edu_bachelors_plus = (
                _safe_int(raw_data.get("edu_bachelors")) +
                _safe_int(raw_data.get("edu_masters")) +
                _safe_int(raw_data.get("edu_professional")) +
                _safe_int(raw_data.get("edu_doctorate"))
            )
            bachelors_pct = (edu_bachelors_plus / edu_total * 100) if edu_total > 0 else None

            labor_force = _safe_int(raw_data.get("labor_force"))
            unemployed = _safe_int(raw_data.get("unemployed"))
            unemployment_rate = (unemployed / labor_force * 100) if labor_force > 0 else None

            tenure_total = _safe_int(raw_data.get("tenure_total"))
            owner_occupied = _safe_int(raw_data.get("owner_occupied"))
            renter_occupied = _safe_int(raw_data.get("renter_occupied"))
            owner_pct = (owner_occupied / tenure_total * 100) if tenure_total > 0 else None
            renter_pct = (renter_occupied / tenure_total * 100) if tenure_total > 0 else None

            total_households = _safe_int(raw_data.get("total_households"))
            family_households = _safe_int(raw_data.get("family_households"))
            family_pct = (family_households / total_households * 100) if total_households > 0 else None

            return DemographicData(
                geography_name=raw_data.get("geography_name", "Unknown"),
                total_population=_safe_int(raw_data.get("total_population")),
                median_household_income=_safe_int(raw_data.get("median_household_income")) or None,
                median_age=_safe_float(raw_data.get("median_age")),
                population_under_18=under_18,
                population_18_34=age_18_34,
                population_35_54=age_35_54,
                population_55_plus=age_55_plus,
                bachelors_degree_or_higher_pct=round(bachelors_pct, 1) if bachelors_pct else None,
                labor_force=labor_force,
                employed=_safe_int(raw_data.get("employed")),
                unemployment_rate=round(unemployment_rate, 1) if unemployment_rate else None,
                total_housing_units=_safe_int(raw_data.get("total_housing_units")),
                owner_occupied_pct=round(owner_pct, 1) if owner_pct else None,
                renter_occupied_pct=round(renter_pct, 1) if renter_pct else None,
                median_home_value=_safe_int(raw_data.get("median_home_value")) or None,
                total_households=total_households,
                avg_household_size=_safe_float(raw_data.get("avg_household_size")),
                family_households_pct=round(family_pct, 1) if family_pct else None,
            )
        except Exception as e:
            print(f"Census API error (subdivision): {e}")
            return None


def format_demographics_report(
    address: str,
    tract_data: DemographicData | None,
    county_data: DemographicData | None,
    subdivision_data: DemographicData | None = None,
) -> str:
    """
    Format demographic data into a readable report for the AI agent.

    Prioritizes subdivision data (town/city level) over tract data when available,
    as it provides more accurate local demographics.
    """
    # Use subdivision data as primary if available (more accurate for town-level analysis)
    primary_data = subdivision_data or tract_data

    if not primary_data and not county_data:
        return f"Unable to retrieve demographic data for {address}. Please verify the address is correct."

    lines = [f"**Trade Area Demographics for {address}**\n"]

    if primary_data:
        # Indicate the geography level
        if subdivision_data:
            lines.append(f"*Town/City: {primary_data.geography_name}*\n")
        else:
            lines.append(f"*Census Tract: {primary_data.geography_name}*\n")

        # Population
        lines.append("**Population & Age:**")
        lines.append(f"- Total Population: {primary_data.total_population:,}")
        if primary_data.median_age:
            lines.append(f"- Median Age: {primary_data.median_age:.1f} years")

        total_pop = primary_data.total_population or 1
        lines.append(f"- Under 18: {primary_data.population_under_18:,} ({primary_data.population_under_18/total_pop*100:.0f}%)")
        lines.append(f"- 18-34: {primary_data.population_18_34:,} ({primary_data.population_18_34/total_pop*100:.0f}%)")
        lines.append(f"- 35-54: {primary_data.population_35_54:,} ({primary_data.population_35_54/total_pop*100:.0f}%)")
        lines.append(f"- 55+: {primary_data.population_55_plus:,} ({primary_data.population_55_plus/total_pop*100:.0f}%)")

        # Income
        lines.append("\n**Income & Economics:**")
        if primary_data.median_household_income:
            lines.append(f"- Median Household Income: ${primary_data.median_household_income:,}")
        if primary_data.unemployment_rate is not None:
            lines.append(f"- Unemployment Rate: {primary_data.unemployment_rate:.1f}%")
        lines.append(f"- Labor Force: {primary_data.labor_force:,}")

        # Education
        lines.append("\n**Education:**")
        if primary_data.bachelors_degree_or_higher_pct:
            lines.append(f"- Bachelor's Degree or Higher: {primary_data.bachelors_degree_or_higher_pct:.1f}%")

        # Housing
        lines.append("\n**Housing:**")
        lines.append(f"- Total Housing Units: {primary_data.total_housing_units:,}")
        if primary_data.owner_occupied_pct:
            lines.append(f"- Owner Occupied: {primary_data.owner_occupied_pct:.1f}%")
        if primary_data.renter_occupied_pct:
            lines.append(f"- Renter Occupied: {primary_data.renter_occupied_pct:.1f}%")
        if primary_data.median_home_value:
            lines.append(f"- Median Home Value: ${primary_data.median_home_value:,}")

        # Households
        lines.append("\n**Households:**")
        lines.append(f"- Total Households: {primary_data.total_households:,}")
        if primary_data.avg_household_size:
            lines.append(f"- Average Household Size: {primary_data.avg_household_size:.2f}")
        if primary_data.family_households_pct:
            lines.append(f"- Family Households: {primary_data.family_households_pct:.1f}%")

    # Add county/region context
    if county_data:
        lines.append(f"\n---\n**Regional Context ({county_data.geography_name}):**")
        lines.append(f"- Regional Population: {county_data.total_population:,}")
        if county_data.median_household_income:
            lines.append(f"- Regional Median Income: ${county_data.median_household_income:,}")
        if county_data.median_home_value:
            lines.append(f"- Regional Median Home Value: ${county_data.median_home_value:,}")

    # Key insights
    lines.append("\n**Key Insights:**")
    if primary_data:
        insights = []
        if primary_data.median_household_income and primary_data.median_household_income > 100000:
            insights.append("High-income area (median >$100K)")
        elif primary_data.median_household_income and primary_data.median_household_income > 75000:
            insights.append("Upper-middle income area")

        if primary_data.bachelors_degree_or_higher_pct and primary_data.bachelors_degree_or_higher_pct > 40:
            insights.append("Highly educated population")

        if primary_data.owner_occupied_pct and primary_data.owner_occupied_pct > 70:
            insights.append("Predominantly owner-occupied (stable residential)")

        young_pct = (primary_data.population_18_34 / total_pop * 100) if total_pop > 0 else 0
        if young_pct > 25:
            insights.append("Strong young adult demographic (18-34)")

        family_pct = primary_data.family_households_pct or 0
        if family_pct > 70:
            insights.append("Family-oriented community")

        if insights:
            for insight in insights:
                lines.append(f"- {insight}")
        else:
            lines.append("- Mixed demographic profile")

    lines.append("\n*Source: U.S. Census Bureau, American Community Survey 5-Year Estimates*")

    return "\n".join(lines)


async def analyze_demographics(location: str) -> str:
    """
    Main entry point for demographics analysis.

    Takes a location (address, town+ZIP, or just ZIP code), geocodes it,
    fetches Census data, and returns a formatted report.

    Now uses the Location Resolver for better handling of city-only inputs
    like "Reno, NV" that don't include a street address or ZIP code.

    Supports:
    - Full street addresses: "123 Main St, Weston, CT 06883"
    - Town + ZIP: "Weston, CT 06883"
    - Town + State: "Weston, CT" or "Reno, NV"
    - Just ZIP code: "06883"

    Args:
        location: Address or location string

    Returns:
        Formatted demographics report string
    """
    from app.services.location_resolver import resolve_location, ResolutionConfidence
    from app.services.analytics import get_analytics, record_tool_start, record_tool_complete

    start_time = record_tool_start("demographics_analysis")

    # Step 1: Use the Location Resolver for unified location handling
    print(f"[CENSUS] Resolving location: {location}")
    resolved = await resolve_location(location)

    # Track the resolution for analytics
    get_analytics().record_location_resolution(
        location_input=location,
        success=resolved.confidence != ResolutionConfidence.LOW,
        method=resolved.method.value if resolved.method else None,
        confidence=resolved.confidence.value if resolved.confidence else None,
    )

    print(f"[CENSUS] Resolved to: {resolved.display_name} (confidence={resolved.confidence.value}, method={resolved.method.value})")

    # Step 2: Try full address geocoding if we have street-level detail
    geography = await geocode_address(location)

    if geography:
        # Full address worked - get detailed demographics
        subdivision_data = await get_subdivision_demographics(geography)
        tract_data = await get_tract_demographics(geography)
        county_data = await get_county_demographics(geography)
        record_tool_complete("demographics_analysis", start_time, success=True)
        return format_demographics_report(location, tract_data, county_data, subdivision_data)

    # Step 3: Use resolved location data
    # Try place-level demographics if we have place FIPS
    if resolved.place_fips and resolved.state_fips:
        print(f"[CENSUS] Attempting place-level query with place_fips={resolved.place_fips}")
        place_data = await get_place_demographics(resolved.state_fips, resolved.place_fips)
        if place_data:
            record_tool_complete("demographics_analysis", start_time, success=True)
            return _format_place_demographics_report(resolved.display_name, place_data, resolved)

    # Step 4: Try ZIP code from resolved location
    zip_code = resolved.primary_zip or _extract_zip_code(location)

    if not zip_code and not resolved.has_zip():
        # No ZIP found by resolver, try legacy lookup
        print(f"[CENSUS] No ZIP in resolved location, attempting legacy lookup for: {location}")
        zip_code = await _lookup_zip_for_location(location)

    if zip_code:
        print(f"[CENSUS] Using ZIP code: {zip_code}")
        zcta_data = await get_zcta_demographics(zip_code)
        if zcta_data:
            record_tool_complete("demographics_analysis", start_time, success=True)
            return _format_zcta_report(location, zcta_data, resolved)

    # Step 5: Try county-level fallback if we have county info
    if resolved.state_fips and resolved.county_fips:
        print(f"[CENSUS] Attempting county-level fallback")
        # Create a minimal geography object for county lookup
        county_geo = CensusGeography(
            address=resolved.display_name,
            latitude=resolved.latitude or 0,
            longitude=resolved.longitude or 0,
            state_fips=resolved.state_fips,
            county_fips=resolved.county_fips,
            tract="",
        )
        county_data = await get_county_demographics(county_geo)
        if county_data:
            record_tool_complete("demographics_analysis", start_time, success=True, metadata={"fallback": "county"})
            lines = [f"**Demographics for {resolved.display_name}**\n"]
            lines.append(f"*County-level data: {county_data.geography_name}*")
            lines.append("*(City-specific data unavailable, showing county-wide statistics)*\n")
            lines.append(_format_demographic_data_section(county_data))
            lines.append("\n*Source: U.S. Census Bureau, American Community Survey 5-Year Estimates*")
            return "\n".join(lines)

    # Step 6: Nothing worked - provide helpful error
    record_tool_complete("demographics_analysis", start_time, success=False)
    return f"""Unable to find demographics for: {location}

**What I tried:**
- Location resolved to: {resolved.display_name}
- Resolution method: {resolved.method.value}
- Confidence: {resolved.confidence.value}

**Tips for better results:**
- Include a ZIP code: "Reno, NV 89501"
- Or use a full address: "100 N Virginia St, Reno, NV 89501"
- Just the ZIP code also works: "89501"

If you're looking for a specific city, try adding the ZIP code of downtown or a major area."""


async def get_place_demographics(state_fips: str, place_fips: str) -> DemographicData | None:
    """
    Fetch ACS demographic data for a Census Place (incorporated city/town).

    This is the preferred method for city-level demographics like "Reno, NV"
    as it provides data specifically for the city boundaries.
    """
    variables = ",".join(ACS_VARIABLES.keys())
    url = f"{CENSUS_ACS_URL}?get=NAME,{variables}&for=place:{place_fips}&in=state:{state_fips}"
    if settings.census_api_key:
        url += f"&key={settings.census_api_key}"

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.get(url)
            response.raise_for_status()
            data = response.json()

            if len(data) < 2:
                return None

            headers = data[0]
            values = data[1]

            raw_data = {}
            for i, header in enumerate(headers):
                if header in ACS_VARIABLES:
                    raw_data[ACS_VARIABLES[header]] = values[i]
                elif header == "NAME":
                    raw_data["geography_name"] = values[i]

            total_pop = _safe_int(raw_data.get("total_population"))
            under_18, age_18_34, age_35_54, age_55_plus = _calculate_age_groups(raw_data, total_pop)

            edu_total = _safe_int(raw_data.get("edu_total_25_plus"))
            edu_bachelors_plus = (
                _safe_int(raw_data.get("edu_bachelors")) +
                _safe_int(raw_data.get("edu_masters")) +
                _safe_int(raw_data.get("edu_professional")) +
                _safe_int(raw_data.get("edu_doctorate"))
            )
            bachelors_pct = (edu_bachelors_plus / edu_total * 100) if edu_total > 0 else None

            labor_force = _safe_int(raw_data.get("labor_force"))
            unemployed = _safe_int(raw_data.get("unemployed"))
            unemployment_rate = (unemployed / labor_force * 100) if labor_force > 0 else None

            tenure_total = _safe_int(raw_data.get("tenure_total"))
            owner_occupied = _safe_int(raw_data.get("owner_occupied"))
            renter_occupied = _safe_int(raw_data.get("renter_occupied"))
            owner_pct = (owner_occupied / tenure_total * 100) if tenure_total > 0 else None
            renter_pct = (renter_occupied / tenure_total * 100) if tenure_total > 0 else None

            total_households = _safe_int(raw_data.get("total_households"))
            family_households = _safe_int(raw_data.get("family_households"))
            family_pct = (family_households / total_households * 100) if total_households > 0 else None

            return DemographicData(
                geography_name=raw_data.get("geography_name", "Unknown"),
                total_population=_safe_int(raw_data.get("total_population")),
                median_household_income=_safe_int(raw_data.get("median_household_income")) or None,
                median_age=_safe_float(raw_data.get("median_age")),
                population_under_18=under_18,
                population_18_34=age_18_34,
                population_35_54=age_35_54,
                population_55_plus=age_55_plus,
                bachelors_degree_or_higher_pct=round(bachelors_pct, 1) if bachelors_pct else None,
                labor_force=labor_force,
                employed=_safe_int(raw_data.get("employed")),
                unemployment_rate=round(unemployment_rate, 1) if unemployment_rate else None,
                total_housing_units=_safe_int(raw_data.get("total_housing_units")),
                owner_occupied_pct=round(owner_pct, 1) if owner_pct else None,
                renter_occupied_pct=round(renter_pct, 1) if renter_pct else None,
                median_home_value=_safe_int(raw_data.get("median_home_value")) or None,
                total_households=total_households,
                avg_household_size=_safe_float(raw_data.get("avg_household_size")),
                family_households_pct=round(family_pct, 1) if family_pct else None,
            )
        except Exception as e:
            print(f"Census API error (place): {e}")
            return None


def _format_demographic_data_section(data: DemographicData) -> str:
    """Format demographic data into report sections."""
    lines = []
    total_pop = data.total_population or 1

    lines.append("**Population & Age:**")
    lines.append(f"- Total Population: {data.total_population:,}")
    if data.median_age:
        lines.append(f"- Median Age: {data.median_age:.1f} years")
    lines.append(f"- Under 18: {data.population_under_18:,} ({data.population_under_18/total_pop*100:.0f}%)")
    lines.append(f"- 18-34: {data.population_18_34:,} ({data.population_18_34/total_pop*100:.0f}%)")
    lines.append(f"- 35-54: {data.population_35_54:,} ({data.population_35_54/total_pop*100:.0f}%)")
    lines.append(f"- 55+: {data.population_55_plus:,} ({data.population_55_plus/total_pop*100:.0f}%)")

    lines.append("\n**Income & Economics:**")
    if data.median_household_income:
        lines.append(f"- Median Household Income: ${data.median_household_income:,}")
    if data.unemployment_rate is not None:
        lines.append(f"- Unemployment Rate: {data.unemployment_rate:.1f}%")
    lines.append(f"- Labor Force: {data.labor_force:,}")

    lines.append("\n**Education:**")
    if data.bachelors_degree_or_higher_pct:
        lines.append(f"- Bachelor's Degree or Higher: {data.bachelors_degree_or_higher_pct:.1f}%")

    lines.append("\n**Housing:**")
    lines.append(f"- Total Housing Units: {data.total_housing_units:,}")
    if data.owner_occupied_pct:
        lines.append(f"- Owner Occupied: {data.owner_occupied_pct:.1f}%")
    if data.renter_occupied_pct:
        lines.append(f"- Renter Occupied: {data.renter_occupied_pct:.1f}%")
    if data.median_home_value:
        lines.append(f"- Median Home Value: ${data.median_home_value:,}")

    lines.append("\n**Households:**")
    lines.append(f"- Total Households: {data.total_households:,}")
    if data.avg_household_size:
        lines.append(f"- Average Household Size: {data.avg_household_size:.2f}")
    if data.family_households_pct:
        lines.append(f"- Family Households: {data.family_households_pct:.1f}%")

    return "\n".join(lines)


def _format_place_demographics_report(display_name: str, data: DemographicData, resolved) -> str:
    """Format a demographics report for place-level data."""
    lines = [f"**Demographics for {display_name}**\n"]
    lines.append(f"*City: {data.geography_name}*\n")
    lines.append(_format_demographic_data_section(data))
    lines.append("\n*Source: U.S. Census Bureau, American Community Survey 5-Year Estimates*")
    return "\n".join(lines)


def _format_zcta_report(location: str, data: DemographicData, resolved) -> str:
    """Format a demographics report for ZCTA (ZIP code) data."""
    lines = [f"**Demographics for {location}**\n"]
    lines.append(f"*ZIP Code Area: {data.geography_name}*")
    if resolved and resolved.used_zip_approximation:
        lines.append("*(Using representative ZIP code for city-level approximation)*")
    lines.append("")
    lines.append(_format_demographic_data_section(data))
    lines.append("\n*Source: U.S. Census Bureau, American Community Survey 5-Year Estimates*")
    return "\n".join(lines)


async def get_zcta_demographics(zip_code: str) -> DemographicData | None:
    """
    Fetch ACS demographic data for a ZIP Code Tabulation Area (ZCTA).

    This allows demographics lookup by ZIP code without needing a street address.
    """
    # Clean the ZIP code (remove any spaces, take first 5 digits)
    zip_code = zip_code.strip().replace(" ", "")[:5]

    if not zip_code.isdigit() or len(zip_code) != 5:
        return None

    variables = ",".join(ACS_VARIABLES.keys())
    url = f"{CENSUS_ACS_URL}?get=NAME,{variables}&for=zip%20code%20tabulation%20area:{zip_code}"
    if settings.census_api_key:
        url += f"&key={settings.census_api_key}"

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.get(url)
            response.raise_for_status()
            data = response.json()

            if len(data) < 2:
                return None

            headers = data[0]
            values = data[1]

            raw_data = {}
            for i, header in enumerate(headers):
                if header in ACS_VARIABLES:
                    raw_data[ACS_VARIABLES[header]] = values[i]
                elif header == "NAME":
                    raw_data["geography_name"] = values[i]

            total_pop = _safe_int(raw_data.get("total_population"))
            under_18, age_18_34, age_35_54, age_55_plus = _calculate_age_groups(raw_data, total_pop)

            edu_total = _safe_int(raw_data.get("edu_total_25_plus"))
            edu_bachelors_plus = (
                _safe_int(raw_data.get("edu_bachelors")) +
                _safe_int(raw_data.get("edu_masters")) +
                _safe_int(raw_data.get("edu_professional")) +
                _safe_int(raw_data.get("edu_doctorate"))
            )
            bachelors_pct = (edu_bachelors_plus / edu_total * 100) if edu_total > 0 else None

            labor_force = _safe_int(raw_data.get("labor_force"))
            unemployed = _safe_int(raw_data.get("unemployed"))
            unemployment_rate = (unemployed / labor_force * 100) if labor_force > 0 else None

            tenure_total = _safe_int(raw_data.get("tenure_total"))
            owner_occupied = _safe_int(raw_data.get("owner_occupied"))
            renter_occupied = _safe_int(raw_data.get("renter_occupied"))
            owner_pct = (owner_occupied / tenure_total * 100) if tenure_total > 0 else None
            renter_pct = (renter_occupied / tenure_total * 100) if tenure_total > 0 else None

            total_households = _safe_int(raw_data.get("total_households"))
            family_households = _safe_int(raw_data.get("family_households"))
            family_pct = (family_households / total_households * 100) if total_households > 0 else None

            return DemographicData(
                geography_name=raw_data.get("geography_name", f"ZCTA {zip_code}"),
                total_population=_safe_int(raw_data.get("total_population")),
                median_household_income=_safe_int(raw_data.get("median_household_income")) or None,
                median_age=_safe_float(raw_data.get("median_age")),
                population_under_18=under_18,
                population_18_34=age_18_34,
                population_35_54=age_35_54,
                population_55_plus=age_55_plus,
                bachelors_degree_or_higher_pct=round(bachelors_pct, 1) if bachelors_pct else None,
                labor_force=labor_force,
                employed=_safe_int(raw_data.get("employed")),
                unemployment_rate=round(unemployment_rate, 1) if unemployment_rate else None,
                total_housing_units=_safe_int(raw_data.get("total_housing_units")),
                owner_occupied_pct=round(owner_pct, 1) if owner_pct else None,
                renter_occupied_pct=round(renter_pct, 1) if renter_pct else None,
                median_home_value=_safe_int(raw_data.get("median_home_value")) or None,
                total_households=total_households,
                avg_household_size=_safe_float(raw_data.get("avg_household_size")),
                family_households_pct=round(family_pct, 1) if family_pct else None,
            )
        except Exception as e:
            print(f"Census API error (ZCTA): {e}")
            return None


def _extract_zip_code(location: str) -> str | None:
    """Extract a 5-digit ZIP code from a location string."""
    import re
    match = re.search(r'\b(\d{5})\b', location)
    return match.group(1) if match else None


async def _lookup_zip_for_location(location: str) -> str | None:
    """
    Look up ZIP code for a location that doesn't include one.

    Uses Google Places API to geocode the location and extract the ZIP code.
    Useful for queries like "downtown Westport" or "Main Street, Fairfield".

    Args:
        location: Location description (town name, neighborhood, etc.)

    Returns:
        5-digit ZIP code string, or None if lookup failed
    """
    import re

    # First check if there's already a ZIP code
    existing_zip = _extract_zip_code(location)
    if existing_zip:
        return existing_zip

    # Use Google Places API to geocode and get full address with ZIP
    if not settings.google_places_api_key:
        return None

    # Add state context for common CT patterns
    search_query = location
    location_lower = location.lower()

    # Common CT towns - add state context if not present
    ct_towns = ["westport", "weston", "fairfield", "norwalk", "stamford",
                "greenwich", "darien", "new canaan", "wilton", "ridgefield",
                "danbury", "bridgeport", "hartford", "new haven", "milford"]

    if any(town in location_lower for town in ct_towns) and "ct" not in location_lower and "connecticut" not in location_lower:
        search_query = f"{location}, CT"

    geocode_url = "https://maps.googleapis.com/maps/api/geocode/json"
    params = {
        "address": search_query,
        "key": settings.google_places_api_key,
    }

    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            response = await client.get(geocode_url, params=params)
            response.raise_for_status()
            data = response.json()

            if data.get("status") == "OK" and data.get("results"):
                # Extract postal code from address components
                for component in data["results"][0].get("address_components", []):
                    if "postal_code" in component.get("types", []):
                        zip_code = component.get("short_name", "")[:5]
                        if zip_code.isdigit() and len(zip_code) == 5:
                            print(f"[CENSUS] Looked up ZIP for '{location}': {zip_code}")
                            return zip_code

            print(f"[CENSUS] Could not find ZIP for '{location}'")
            return None
        except Exception as e:
            print(f"[CENSUS] ZIP lookup error: {e}")
            return None


async def get_demographics_structured(location: str) -> dict | None:
    """
    Get demographics data as a structured dictionary for use by other agents.

    Supports full addresses, town+ZIP, or just ZIP codes.

    Args:
        location: Address or location string

    Returns:
        Dict with demographics data, or None if lookup failed
    """
    # Try geocoding first
    geography = await geocode_address(location)

    if geography:
        # Prefer subdivision data, fallback to tract
        subdivision_data = await get_subdivision_demographics(geography)
        tract_data = await get_tract_demographics(geography)
        data = subdivision_data or tract_data
    else:
        # Try ZIP code fallback
        zip_code = _extract_zip_code(location)
        if not zip_code:
            # Try to look up ZIP from location name
            zip_code = await _lookup_zip_for_location(location)
        if zip_code:
            data = await get_zcta_demographics(zip_code)
        else:
            return None

    if not data:
        return None

    return {
        "geography_name": data.geography_name,
        "population": data.total_population,
        "households": data.total_households,
        "median_income": data.median_household_income,
        "median_age": data.median_age,
        "population_under_18": data.population_under_18,
        "population_18_34": data.population_18_34,
        "population_35_54": data.population_35_54,
        "population_55_plus": data.population_55_plus,
        "bachelors_degree_pct": data.bachelors_degree_or_higher_pct,
        "unemployment_rate": data.unemployment_rate,
        "owner_occupied_pct": data.owner_occupied_pct,
        "median_home_value": data.median_home_value,
        "avg_household_size": data.avg_household_size,
        "source": "US Census ACS",
    }
