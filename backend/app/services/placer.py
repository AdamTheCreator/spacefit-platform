"""
Placer.ai API Service

Provides foot traffic, visitor demographics, void analysis, and tenant match data
from Placer.ai's API. This captures ACTUAL visitors (via mobile data) rather than
just residents within a radius - a key distinction from Census demographics.

Key difference from Census:
- Census = people living within radius
- Placer.ai = actual customers visiting the location (mobile data)
  "I might drive 20 miles to go to a Fills" - so customer profile can differ from demographics
"""

import httpx
from typing import Any
from dataclasses import dataclass
from datetime import datetime
from app.core.config import settings


# Placer.ai API base URL
PLACER_API_URL = "https://api.placer.ai/v1"


@dataclass
class AudienceOverview:
    """Customer profile based on actual visitors (mobile data)."""
    venue_id: str
    venue_name: str
    address: str
    # Demographics of actual visitors
    median_household_income: int | None
    median_age: float | None
    # Gender split
    male_pct: float
    female_pct: float
    # Age distribution
    age_18_24_pct: float
    age_25_34_pct: float
    age_35_44_pct: float
    age_45_54_pct: float
    age_55_plus_pct: float
    # Education
    bachelors_degree_pct: float | None
    # Ethnicity (most common)
    most_common_ethnicity: str | None
    # Household size
    avg_household_size: float | None


@dataclass
class FootTrafficData:
    """Foot traffic metrics for a location."""
    venue_id: str
    venue_name: str
    address: str
    # Traffic counts
    monthly_visitors: int
    daily_avg_visitors: int
    vehicles_per_day: int | None  # VPD - important for retail
    # Peak times
    peak_day: str  # e.g., "Saturday"
    peak_hour: str  # e.g., "2:00 PM"
    # Trends
    year_over_year_change_pct: float | None
    # Dwell time
    avg_dwell_time_minutes: float | None
    # Trade area
    visitor_radius_miles: float  # How far visitors travel


@dataclass
class TimeFilteredTraffic:
    """Traffic filtered by time of day (e.g., 7am-10am for coffee)."""
    venue_id: str
    time_start: str
    time_end: str
    avg_visitors: int
    pct_of_daily_total: float


@dataclass
class VoidOpportunity:
    """A tenant void opportunity identified by Placer.ai."""
    category: str  # e.g., "Fast Food", "Coffee", "Fitness"
    tenant_name: str  # e.g., "Dairy Queen", "Dutch Bros"
    nearest_location: str | None  # e.g., "Downtown Stamford"
    distance_miles: float | None  # e.g., 3.2
    match_score: float  # 0-100, how well this tenant matches the customer profile
    contact_email: str | None  # Expansion contact if available


@dataclass
class TenantMatch:
    """A tenant match suggestion based on customer profile."""
    tenant_name: str
    category: str
    match_score: float  # 0-100
    rationale: str  # Why this tenant matches
    existing_locations: int  # How many locations they have
    expansion_status: str  # "Actively expanding", "Selective", "Not expanding"


async def search_venue(address: str) -> str | None:
    """
    Search for a Placer.ai venue ID by address.

    Args:
        address: Property address or name

    Returns:
        venue_id string, or None if not found
    """
    if not settings.placer_api_key:
        print("[PLACER] API key not configured - using stub data")
        return "stub_venue_12345"

    url = f"{PLACER_API_URL}/venues/search"
    headers = {"Authorization": f"Bearer {settings.placer_api_key}"}
    params = {"query": address, "limit": 1}

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.get(url, headers=headers, params=params)
            response.raise_for_status()
            data = response.json()

            if data.get("venues"):
                return data["venues"][0].get("id")
            return None
        except Exception as e:
            print(f"[PLACER] Venue search error: {e}")
            return None


async def get_audience_overview(venue_id: str) -> AudienceOverview | None:
    """
    Get customer profile for a venue - actual visitors via mobile data.

    This is the "Audience Overview" feature from Placer.ai that shows
    who actually visits the location, not just who lives nearby.
    """
    if not settings.placer_api_key:
        # Return stub data for development
        return AudienceOverview(
            venue_id=venue_id,
            venue_name="Sample Shopping Center",
            address="123 Main St",
            median_household_income=85000,
            median_age=38.5,
            male_pct=42.0,
            female_pct=58.0,
            age_18_24_pct=12.0,
            age_25_34_pct=24.0,
            age_35_44_pct=28.0,
            age_45_54_pct=20.0,
            age_55_plus_pct=16.0,
            bachelors_degree_pct=45.0,
            most_common_ethnicity="White/Caucasian",
            avg_household_size=2.8,
        )

    url = f"{PLACER_API_URL}/venues/{venue_id}/audience"
    headers = {"Authorization": f"Bearer {settings.placer_api_key}"}

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            data = response.json()

            # Parse API response into our dataclass
            # NOTE: Actual field names may differ - adjust based on real API docs
            return AudienceOverview(
                venue_id=venue_id,
                venue_name=data.get("venue_name", "Unknown"),
                address=data.get("address", ""),
                median_household_income=data.get("median_hh_income"),
                median_age=data.get("median_age"),
                male_pct=data.get("gender_male_pct", 0),
                female_pct=data.get("gender_female_pct", 0),
                age_18_24_pct=data.get("age_18_24_pct", 0),
                age_25_34_pct=data.get("age_25_34_pct", 0),
                age_35_44_pct=data.get("age_35_44_pct", 0),
                age_45_54_pct=data.get("age_45_54_pct", 0),
                age_55_plus_pct=data.get("age_55_plus_pct", 0),
                bachelors_degree_pct=data.get("bachelors_pct"),
                most_common_ethnicity=data.get("top_ethnicity"),
                avg_household_size=data.get("avg_hh_size"),
            )
        except Exception as e:
            print(f"[PLACER] Audience overview error: {e}")
            return None


async def get_foot_traffic(
    venue_id: str,
    time_filter: str | None = None,
) -> FootTrafficData | None:
    """
    Get foot traffic data including VPD (vehicles per day).

    Args:
        venue_id: Placer.ai venue ID
        time_filter: Optional time filter like "7am-10am" for coffee tenants

    Returns:
        FootTrafficData with visitor counts, VPD, peak times
    """
    if not settings.placer_api_key:
        # Return stub data for development
        return FootTrafficData(
            venue_id=venue_id,
            venue_name="Sample Shopping Center",
            address="123 Main St",
            monthly_visitors=285000,
            daily_avg_visitors=9500,
            vehicles_per_day=12500,
            peak_day="Saturday",
            peak_hour="2:00 PM",
            year_over_year_change_pct=8.2,
            avg_dwell_time_minutes=47,
            visitor_radius_miles=8.5,
        )

    url = f"{PLACER_API_URL}/venues/{venue_id}/traffic"
    headers = {"Authorization": f"Bearer {settings.placer_api_key}"}
    params = {}
    if time_filter:
        params["time_filter"] = time_filter

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.get(url, headers=headers, params=params)
            response.raise_for_status()
            data = response.json()

            return FootTrafficData(
                venue_id=venue_id,
                venue_name=data.get("venue_name", "Unknown"),
                address=data.get("address", ""),
                monthly_visitors=data.get("monthly_visits", 0),
                daily_avg_visitors=data.get("daily_avg", 0),
                vehicles_per_day=data.get("vpd"),
                peak_day=data.get("peak_day", "Unknown"),
                peak_hour=data.get("peak_hour", "Unknown"),
                year_over_year_change_pct=data.get("yoy_change"),
                avg_dwell_time_minutes=data.get("dwell_time"),
                visitor_radius_miles=data.get("trade_area_radius", 5),
            )
        except Exception as e:
            print(f"[PLACER] Foot traffic error: {e}")
            return None


async def get_void_analysis(venue_id: str) -> list[VoidOpportunity]:
    """
    Get void analysis showing missing tenant categories with distance to nearest.

    This is the key feature that shows:
    - What tenant categories are missing
    - How far away the nearest location is
    - Contact info for tenant expansion teams
    """
    if not settings.placer_api_key:
        # Return stub data for development - matches partner's example
        return [
            VoidOpportunity(
                category="Fast Food",
                tenant_name="Dairy Queen",
                nearest_location=None,
                distance_miles=3.0,
                match_score=85.0,
                contact_email="realestate@dairyqueen.com",
            ),
            VoidOpportunity(
                category="Fast Food",
                tenant_name="Bojangles",
                nearest_location="Route 1 Plaza",
                distance_miles=7.0,
                match_score=78.0,
                contact_email="expansion@bojangles.com",
            ),
            VoidOpportunity(
                category="Fast Casual",
                tenant_name="Cava",
                nearest_location=None,
                distance_miles=None,
                match_score=92.0,
                contact_email="realestate@cava.com",
            ),
            VoidOpportunity(
                category="Fast Casual",
                tenant_name="Sweetgreen",
                nearest_location="Downtown",
                distance_miles=4.2,
                match_score=88.0,
                contact_email="sites@sweetgreen.com",
            ),
            VoidOpportunity(
                category="Coffee",
                tenant_name="Dutch Bros",
                nearest_location=None,
                distance_miles=None,
                match_score=90.0,
                contact_email="realestate@dutchbros.com",
            ),
            VoidOpportunity(
                category="Fitness",
                tenant_name="Orangetheory",
                nearest_location="Stamford",
                distance_miles=5.5,
                match_score=82.0,
                contact_email="realestate@orangetheory.com",
            ),
            VoidOpportunity(
                category="Fitness",
                tenant_name="F45",
                nearest_location=None,
                distance_miles=None,
                match_score=79.0,
                contact_email="franchise@f45training.com",
            ),
        ]

    url = f"{PLACER_API_URL}/venues/{venue_id}/voids"
    headers = {"Authorization": f"Bearer {settings.placer_api_key}"}

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            data = response.json()

            voids = []
            for item in data.get("voids", []):
                voids.append(VoidOpportunity(
                    category=item.get("category", "Unknown"),
                    tenant_name=item.get("tenant_name", "Unknown"),
                    nearest_location=item.get("nearest_location"),
                    distance_miles=item.get("distance_miles"),
                    match_score=item.get("match_score", 0),
                    contact_email=item.get("contact_email"),
                ))
            return voids
        except Exception as e:
            print(f"[PLACER] Void analysis error: {e}")
            return []


async def get_tenant_match(venue_id: str) -> list[TenantMatch]:
    """
    Get tenant match suggestions based on customer profile.

    This uses Placer.ai's matching algorithm to suggest tenants
    whose customer profile matches the venue's visitor base.
    """
    if not settings.placer_api_key:
        # Return stub data for development
        return [
            TenantMatch(
                tenant_name="Cava",
                category="Fast Casual",
                match_score=92.0,
                rationale="High-income, health-conscious visitors align with Cava's target demo",
                existing_locations=285,
                expansion_status="Actively expanding",
            ),
            TenantMatch(
                tenant_name="Dutch Bros",
                category="Coffee",
                match_score=90.0,
                rationale="Young adult demographic (25-34) matches Dutch Bros core customer",
                existing_locations=750,
                expansion_status="Actively expanding",
            ),
            TenantMatch(
                tenant_name="Orangetheory Fitness",
                category="Fitness",
                match_score=85.0,
                rationale="Affluent, health-focused visitors match OTF member profile",
                existing_locations=1500,
                expansion_status="Selective",
            ),
        ]

    url = f"{PLACER_API_URL}/venues/{venue_id}/tenant-match"
    headers = {"Authorization": f"Bearer {settings.placer_api_key}"}

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            data = response.json()

            matches = []
            for item in data.get("matches", []):
                matches.append(TenantMatch(
                    tenant_name=item.get("tenant_name", "Unknown"),
                    category=item.get("category", "Unknown"),
                    match_score=item.get("match_score", 0),
                    rationale=item.get("rationale", ""),
                    existing_locations=item.get("location_count", 0),
                    expansion_status=item.get("expansion_status", "Unknown"),
                ))
            return matches
        except Exception as e:
            print(f"[PLACER] Tenant match error: {e}")
            return []


def format_audience_report(audience: AudienceOverview) -> str:
    """Format audience overview as markdown for chat display."""
    lines = [
        f"**Customer Profile for {audience.venue_name}**\n",
        "*Based on actual visitors (mobile data), not just nearby residents*\n",
        "**Visitor Demographics:**",
        f"- Median Household Income: ${audience.median_household_income:,}" if audience.median_household_income else "",
        f"- Median Age: {audience.median_age:.1f} years" if audience.median_age else "",
        f"- Most Common Education: {'Bachelor\'s degree or higher' if audience.bachelors_degree_pct and audience.bachelors_degree_pct > 40 else 'Some college'}",
        f"- Most Common Ethnicity: {audience.most_common_ethnicity}" if audience.most_common_ethnicity else "",
        "",
        "**Gender Split:**",
        f"- Female: {audience.female_pct:.0f}%",
        f"- Male: {audience.male_pct:.0f}%",
        "",
        "**Age Distribution:**",
        f"- 18-24: {audience.age_18_24_pct:.0f}%",
        f"- 25-34: {audience.age_25_34_pct:.0f}%",
        f"- 35-44: {audience.age_35_44_pct:.0f}%",
        f"- 45-54: {audience.age_45_54_pct:.0f}%",
        f"- 55+: {audience.age_55_plus_pct:.0f}%",
        "",
        f"**Avg Household Size:** {audience.avg_household_size:.1f}" if audience.avg_household_size else "",
        "",
        "*Source: Placer.ai mobile data*",
    ]
    return "\n".join(line for line in lines if line)


def format_foot_traffic_report(traffic: FootTrafficData) -> str:
    """Format foot traffic data as markdown for chat display."""
    lines = [
        f"**Foot Traffic Analysis for {traffic.venue_name}**\n",
        "**Visitor Volume:**",
        f"- Monthly Visitors: {traffic.monthly_visitors:,}",
        f"- Daily Average: {traffic.daily_avg_visitors:,}",
    ]

    if traffic.vehicles_per_day:
        lines.append(f"- Vehicles Per Day (VPD): {traffic.vehicles_per_day:,}")

    lines.extend([
        "",
        "**Peak Times:**",
        f"- Peak Day: {traffic.peak_day}",
        f"- Peak Hour: {traffic.peak_hour}",
    ])

    if traffic.year_over_year_change_pct is not None:
        trend = "+" if traffic.year_over_year_change_pct > 0 else ""
        lines.append(f"\n**Year-over-Year Change:** {trend}{traffic.year_over_year_change_pct:.1f}%")

    if traffic.avg_dwell_time_minutes:
        lines.append(f"**Avg Dwell Time:** {traffic.avg_dwell_time_minutes:.0f} minutes")

    lines.append(f"**Trade Area Radius:** {traffic.visitor_radius_miles:.1f} miles")
    lines.append("\n*Source: Placer.ai mobile data*")

    return "\n".join(lines)


def format_void_analysis_report(address: str, voids: list[VoidOpportunity]) -> str:
    """
    Format void analysis as markdown with category breakdown and contact info.

    This matches the format partner showed from Sites USA:
    Category: Fast Food
    - Dairy Queen: Nearest 3 miles, Contact: [email]
    """
    if not voids:
        return f"No void opportunities identified for {address}."

    lines = [
        f"**Void Analysis for {address}**\n",
        "*Missing tenant categories based on customer profile match*\n",
    ]

    # Group voids by category
    categories: dict[str, list[VoidOpportunity]] = {}
    for void in voids:
        if void.category not in categories:
            categories[void.category] = []
        categories[void.category].append(void)

    # Sort categories by highest match score in each
    sorted_categories = sorted(
        categories.items(),
        key=lambda x: max(v.match_score for v in x[1]),
        reverse=True
    )

    for category, category_voids in sorted_categories:
        # Sort voids within category by match score
        sorted_voids = sorted(category_voids, key=lambda x: x.match_score, reverse=True)

        lines.append(f"\n**{category}**")
        lines.append("| Tenant | Nearest Location | Distance | Match | Contact |")
        lines.append("|--------|------------------|----------|-------|---------|")

        for void in sorted_voids:
            nearest = void.nearest_location or "None in market"
            distance = f"{void.distance_miles:.1f} mi" if void.distance_miles else "-"
            contact = void.contact_email or "-"
            lines.append(f"| {void.tenant_name} | {nearest} | {distance} | {void.match_score:.0f}% | {contact} |")

    lines.append("\n*Source: Placer.ai void analysis*")
    return "\n".join(lines)


async def analyze_foot_traffic(address: str) -> str:
    """
    Main entry point for foot traffic analysis.

    Searches for venue by address, then returns formatted report.
    """
    venue_id = await search_venue(address)
    if not venue_id:
        return f"Could not find venue for: {address}. Please try a more specific address or shopping center name."

    traffic = await get_foot_traffic(venue_id)
    if not traffic:
        return f"Could not retrieve foot traffic data for: {address}"

    return format_foot_traffic_report(traffic)


async def analyze_customer_profile(address: str) -> str:
    """
    Get customer profile (audience overview) for a location.

    This shows actual visitor demographics, not just residents.
    """
    venue_id = await search_venue(address)
    if not venue_id:
        return f"Could not find venue for: {address}"

    audience = await get_audience_overview(venue_id)
    if not audience:
        return f"Could not retrieve customer profile for: {address}"

    return format_audience_report(audience)


async def analyze_voids(address: str) -> str:
    """
    Get void analysis with tenant opportunities and contact info.
    """
    venue_id = await search_venue(address)
    if not venue_id:
        return f"Could not find venue for: {address}"

    voids = await get_void_analysis(venue_id)
    return format_void_analysis_report(address, voids)


async def get_void_opportunities_structured(address: str) -> list[dict] | None:
    """
    Get void opportunities as structured data for use by email blast feature.

    Returns list of dicts with tenant name, category, distance, contact email.
    """
    venue_id = await search_venue(address)
    if not venue_id:
        return None

    voids = await get_void_analysis(venue_id)
    if not voids:
        return None

    return [
        {
            "tenant_name": v.tenant_name,
            "category": v.category,
            "nearest_location": v.nearest_location,
            "distance_miles": v.distance_miles,
            "match_score": v.match_score,
            "contact_email": v.contact_email,
        }
        for v in voids
    ]
