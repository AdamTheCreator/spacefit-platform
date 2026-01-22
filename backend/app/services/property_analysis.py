"""
Property Analysis Service

Orchestrates comprehensive property analysis by:
1. Geocoding the property address
2. Pulling real demographics from Census API
3. Searching for competitors via Google Places
4. Running void analysis with real data
5. Generating investment memos

This is the main entry point for document-based analysis.
"""

from dataclasses import dataclass, asdict
from typing import Any

from app.services.census import (
    geocode_address as census_geocode,
    analyze_demographics,
    CensusGeography,
    DemographicData,
    get_tract_demographics,
    get_county_demographics,
    get_subdivision_demographics,
)
from app.services.places import (
    geocode_address as places_geocode,
    search_nearby_businesses,
    get_area_businesses,
    Business,
)
from app.agents.void_analysis import analyze_voids_for_property
from app.agents.investment_memo import generate_investment_memo


@dataclass
class PropertyContext:
    """Complete context for a property analysis."""
    # Property info from flyer
    property_name: str | None = None
    address: str | None = None
    city: str | None = None
    state: str | None = None
    zip_code: str | None = None
    property_type: str | None = None
    total_sf: int | None = None
    available_sf: int | None = None

    # Geocoded location
    latitude: float | None = None
    longitude: float | None = None

    # Existing tenants from flyer
    existing_tenants: list[dict] | None = None

    # Available spaces from flyer
    available_spaces: list[dict] | None = None

    @property
    def full_address(self) -> str:
        """Build full address string."""
        parts = []
        if self.address:
            parts.append(self.address)
        if self.city:
            parts.append(self.city)
        if self.state:
            parts.append(self.state)
        if self.zip_code:
            parts.append(self.zip_code)
        return ", ".join(parts) if parts else ""


@dataclass
class AnalysisResult:
    """Complete analysis result."""
    property_context: PropertyContext
    demographics: dict | None = None
    competitors: list[dict] | None = None
    void_analysis: dict | None = None
    investment_memo: dict | None = None
    errors: list[str] | None = None


def extract_property_context_from_document(extracted_data: dict) -> PropertyContext:
    """
    Extract PropertyContext from a parsed document's extracted_data.

    Args:
        extracted_data: The extracted_data field from ParsedDocument

    Returns:
        PropertyContext with all available property info
    """
    property_info = extracted_data.get("property_info", {})

    # Extract existing tenants
    existing_tenants = []
    for tenant in extracted_data.get("existing_tenants", []):
        existing_tenants.append({
            "name": tenant.get("name"),
            "category": tenant.get("category"),
            "square_footage": tenant.get("square_footage"),
            "is_anchor": tenant.get("is_anchor", False),
            "is_national": tenant.get("is_national", False),
        })

    # Extract available spaces
    available_spaces = []
    for space in extracted_data.get("available_spaces", []):
        available_spaces.append({
            "suite_number": space.get("suite_number"),
            "square_footage": space.get("square_footage"),
            "asking_rent_psf": space.get("asking_rent_psf"),
            "building_address": space.get("building_address"),
            "is_anchor": space.get("is_anchor", False),
            "is_endcap": space.get("is_endcap", False),
            "has_drive_thru": space.get("has_drive_thru", False),
        })

    # Calculate total available SF
    total_available = sum(s.get("square_footage") or 0 for s in available_spaces)

    return PropertyContext(
        property_name=property_info.get("name"),
        address=property_info.get("address"),
        city=property_info.get("city"),
        state=property_info.get("state"),
        zip_code=property_info.get("zip_code"),
        property_type=property_info.get("property_type"),
        total_sf=property_info.get("total_sf") or property_info.get("gla_sf"),
        available_sf=total_available or property_info.get("available_sf"),
        existing_tenants=existing_tenants if existing_tenants else None,
        available_spaces=available_spaces if available_spaces else None,
    )


async def geocode_property(context: PropertyContext) -> PropertyContext:
    """
    Geocode the property address and update the context.

    Tries Census geocoder first (free), falls back to Google.
    """
    if not context.full_address:
        return context

    # Try Census geocoder first (free and reliable)
    geo = await census_geocode(context.full_address)
    if geo:
        context.latitude = geo.latitude
        context.longitude = geo.longitude
        return context

    # Fallback to Google Places geocoder
    coords = await places_geocode(context.full_address)
    if coords:
        context.latitude, context.longitude = coords

    return context


async def get_demographics_for_property(
    context: PropertyContext,
    radius_miles: float = 3.0,
) -> dict | None:
    """
    Get demographics data for a property.

    Returns structured demographics dict for use in void analysis.
    """
    if not context.full_address:
        return None

    # First geocode to get Census geography
    geo = await census_geocode(context.full_address)
    if not geo:
        return None

    # Get subdivision (town) level data - most accurate
    subdivision_data = await get_subdivision_demographics(geo)

    # Get tract level as fallback
    tract_data = await get_tract_demographics(geo)

    # Get county for context
    county_data = await get_county_demographics(geo)

    # Use subdivision data if available, otherwise tract
    primary = subdivision_data or tract_data

    if not primary:
        return None

    return {
        "radius_miles": radius_miles,
        "population": primary.total_population,
        "households": primary.total_households,
        "median_income": primary.median_household_income,
        "median_age": primary.median_age,
        "owner_occupied_pct": primary.owner_occupied_pct,
        "bachelors_plus_pct": primary.bachelors_degree_or_higher_pct,
        "unemployment_rate": primary.unemployment_rate,
        "labor_force": primary.labor_force,
        "family_households_pct": primary.family_households_pct,
        "geography_name": primary.geography_name,
        # Age distribution
        "pop_under_18": primary.population_under_18,
        "pop_18_34": primary.population_18_34,
        "pop_35_54": primary.population_35_54,
        "pop_55_plus": primary.population_55_plus,
        # Regional context
        "regional_population": county_data.total_population if county_data else None,
        "regional_median_income": county_data.median_household_income if county_data else None,
    }


async def get_competitors_for_property(
    context: PropertyContext,
    radius_meters: int = 3000,  # ~2 miles
) -> list[dict]:
    """
    Get competitor businesses near the property.

    Returns list of businesses with categories for void analysis.
    """
    if not context.latitude or not context.longitude:
        # Try to geocode first
        context = await geocode_property(context)

    if not context.latitude or not context.longitude:
        return []

    # Search for nearby businesses
    businesses = await search_nearby_businesses(
        latitude=context.latitude,
        longitude=context.longitude,
        radius_meters=radius_meters,
    )

    # Convert to dicts for void analysis
    competitor_list = []
    for biz in businesses:
        competitor_list.append({
            "name": biz.name,
            "category": biz.category,
            "address": biz.address,
            "rating": biz.rating,
            "types": biz.types,
        })

    return competitor_list


async def run_comprehensive_analysis(
    context: PropertyContext,
    include_demographics: bool = True,
    include_competitors: bool = True,
    include_void_analysis: bool = True,
    include_memo: bool = False,
    radius_miles: float = 3.0,
) -> AnalysisResult:
    """
    Run comprehensive property analysis.

    This is the main entry point that orchestrates all analysis steps.

    Args:
        context: PropertyContext with property info from flyer
        include_demographics: Whether to pull Census demographics
        include_competitors: Whether to search for nearby competitors
        include_void_analysis: Whether to run void/gap analysis
        include_memo: Whether to generate investment memo
        radius_miles: Trade area radius for demographics

    Returns:
        AnalysisResult with all analysis data
    """
    errors = []
    result = AnalysisResult(property_context=context, errors=[])

    # Step 1: Geocode the property
    context = await geocode_property(context)
    if not context.latitude or not context.longitude:
        errors.append(f"Could not geocode address: {context.full_address}")

    # Step 2: Get demographics
    demographics = None
    if include_demographics:
        try:
            demographics = await get_demographics_for_property(context, radius_miles)
            result.demographics = demographics
            if not demographics:
                errors.append("Could not retrieve demographics data")
        except Exception as e:
            errors.append(f"Demographics error: {str(e)}")

    # Step 3: Get competitors
    competitors = None
    if include_competitors:
        try:
            competitors = await get_competitors_for_property(
                context,
                radius_meters=int(radius_miles * 1609),  # Convert miles to meters
            )
            result.competitors = competitors
            if not competitors:
                errors.append("No competitors found in trade area")
        except Exception as e:
            errors.append(f"Competitor search error: {str(e)}")

    # Step 4: Run void analysis with real data
    if include_void_analysis:
        try:
            void_analysis = await analyze_voids_for_property(
                address=context.full_address,
                existing_tenants=context.existing_tenants,
                demographics=demographics,
                radius_miles=radius_miles,
            )
            result.void_analysis = void_analysis
        except Exception as e:
            errors.append(f"Void analysis error: {str(e)}")

    # Step 5: Generate investment memo
    if include_memo:
        try:
            memo = await generate_investment_memo(
                property_info={
                    "name": context.property_name,
                    "address": context.address,
                    "city": context.city,
                    "state": context.state,
                    "zip_code": context.zip_code,
                    "total_sf": context.total_sf,
                    "available_sf": context.available_sf,
                    "property_type": context.property_type,
                },
                demographics=demographics,
                tenant_roster=context.existing_tenants,
                void_analysis=result.void_analysis,
            )
            result.investment_memo = memo
        except Exception as e:
            errors.append(f"Investment memo error: {str(e)}")

    result.errors = errors if errors else None
    return result


async def analyze_document(
    document_id: str,
    db_session,
    include_demographics: bool = True,
    include_competitors: bool = True,
    include_void_analysis: bool = True,
    radius_miles: float = 3.0,
) -> AnalysisResult:
    """
    Run analysis for a specific document in the database.

    Args:
        document_id: ID of the ParsedDocument
        db_session: Database session
        include_demographics: Whether to pull Census demographics
        include_competitors: Whether to search for nearby competitors
        include_void_analysis: Whether to run void/gap analysis
        radius_miles: Trade area radius

    Returns:
        AnalysisResult with all analysis data
    """
    from sqlalchemy import select
    from app.db.models.document import ParsedDocument

    # Get the document
    result = await db_session.execute(
        select(ParsedDocument).where(ParsedDocument.id == document_id)
    )
    document = result.scalar_one_or_none()

    if not document:
        return AnalysisResult(
            property_context=PropertyContext(),
            errors=["Document not found"],
        )

    if not document.extracted_data:
        return AnalysisResult(
            property_context=PropertyContext(),
            errors=["Document has no extracted data"],
        )

    # Extract property context from document
    context = extract_property_context_from_document(document.extracted_data)

    # Run comprehensive analysis
    return await run_comprehensive_analysis(
        context=context,
        include_demographics=include_demographics,
        include_competitors=include_competitors,
        include_void_analysis=include_void_analysis,
        radius_miles=radius_miles,
    )
