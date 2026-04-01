"""
Google Places API Service

Provides real business/tenant data for locations using Google Places API.
Used by the Tenant Roster Agent to get actual businesses at a location.
"""

import asyncio
import httpx
import logging
from dataclasses import dataclass, field
from typing import Any
from app.core.config import settings
from app.services.location_resolver import resolve_location

logger = logging.getLogger(__name__)

# Google Places API endpoints (using legacy API which is more widely enabled)
PLACES_NEARBY_URL = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
PLACES_TEXT_SEARCH_URL = "https://maps.googleapis.com/maps/api/place/textsearch/json"
GEOCODE_URL = "https://maps.googleapis.com/maps/api/geocode/json"

# Conversion constant
METERS_PER_MILE = 1609.34

# Known-defunct businesses that Google Places sometimes still marks as operational
DEFUNCT_BUSINESS_NAMES = {
    "bed bath & beyond", "bed bath and beyond",
    "buy buy baby",
    "christmas tree shops",
    "pier 1 imports", "pier 1",
    "papyrus",
    "dressbarn", "dress barn",
    "charming charlie",
    "tuesday morning",
    "stein mart",
    "destination xl", "destination maternity",
    "forever 21",  # many locations closed — kept as safety net
    "radioshack", "radio shack",
    "toys r us", "toys \"r\" us", "babies r us", "babies \"r\" us",
    "modell's sporting goods", "modells",
    "lord & taylor", "lord and taylor",
    "neiman marcus last call",
    "sears", "kmart", "k-mart",
}


# Business type categories for commercial real estate analysis
CATEGORY_MAPPING = {
    # Retail
    "clothing_store": "Retail - Apparel",
    "shoe_store": "Retail - Apparel",
    "jewelry_store": "Retail - Apparel",
    "department_store": "Retail - Department Store",
    "shopping_mall": "Retail - Shopping Center",
    "furniture_store": "Retail - Home",
    "home_goods_store": "Retail - Home",
    "home_improvement_store": "Retail - Home",
    "hardware_store": "Retail - Home",
    "electronics_store": "Retail - Electronics",
    "book_store": "Retail - Books & Media",
    "pet_store": "Retail - Pet",
    "sporting_goods_store": "Retail - Sporting Goods",
    "convenience_store": "Retail - Convenience",
    "grocery_store": "Grocery",
    "supermarket": "Grocery",
    "liquor_store": "Retail - Liquor",
    "pharmacy": "Pharmacy/Health",
    "drugstore": "Pharmacy/Health",

    # Dining
    "restaurant": "Dining - Restaurant",
    "fast_food_restaurant": "Dining - Fast Food",
    "cafe": "Dining - Cafe",
    "coffee_shop": "Dining - Coffee",
    "bakery": "Dining - Bakery",
    "bar": "Dining - Bar",
    "meal_delivery": "Dining - Delivery",
    "meal_takeaway": "Dining - Takeaway",
    "ice_cream_shop": "Dining - Dessert",

    # Services
    "bank": "Services - Financial",
    "atm": "Services - Financial",
    "insurance_agency": "Services - Financial",
    "accounting": "Services - Financial",
    "real_estate_agency": "Services - Real Estate",
    "lawyer": "Services - Legal",
    "doctor": "Services - Medical",
    "dentist": "Services - Medical",
    "veterinary_care": "Services - Pet",
    "hair_care": "Services - Personal Care",
    "beauty_salon": "Services - Personal Care",
    "spa": "Services - Personal Care",
    "gym": "Services - Fitness",
    "laundry": "Services - Laundry",
    "car_wash": "Services - Auto",
    "car_repair": "Services - Auto",
    "car_dealer": "Services - Auto",
    "gas_station": "Services - Auto",

    # Entertainment
    "movie_theater": "Entertainment",
    "bowling_alley": "Entertainment",
    "amusement_park": "Entertainment",
    "night_club": "Entertainment",

    # Other
    "post_office": "Government/Civic",
    "local_government_office": "Government/Civic",
    "library": "Government/Civic",
    "school": "Education",
    "university": "Education",
    "church": "Religious",
    "mosque": "Religious",
    "synagogue": "Religious",
    "hotel": "Lodging",
    "lodging": "Lodging",
}


def miles_to_meters(miles: float) -> int:
    """Convert miles to meters for Google Places API radius parameter."""
    return int(miles * METERS_PER_MILE)


def _is_defunct_business(name: str) -> bool:
    """Check if a business name matches the known-defunct blacklist."""
    name_lower = name.lower().strip()
    return any(defunct in name_lower for defunct in DEFUNCT_BUSINESS_NAMES)


@dataclass
class Business:
    """Represents a business/tenant."""
    name: str
    address: str
    category: str
    types: list[str]
    rating: float | None = None
    user_ratings_total: int | None = None
    price_level: int | None = None
    is_open: bool | None = None
    phone: str | None = None
    website: str | None = None
    place_id: str | None = None
    business_status: str | None = None


@dataclass
class LocationData:
    """Data about a location and its businesses."""
    address: str
    latitude: float
    longitude: float
    businesses: list[Business] = field(default_factory=list)
    total_found: int = 0


def _categorize_business(types: list[str]) -> str:
    """Categorize a business based on its Google Place types."""
    for place_type in types:
        if place_type in CATEGORY_MAPPING:
            return CATEGORY_MAPPING[place_type]
    return "Other"


async def geocode_address(address: str) -> tuple[float, float] | None:
    """
    Convert an address to lat/lng coordinates.

    Tries Google Geocoding API first, falls back to Census Geocoder.

    Returns (latitude, longitude) or None if geocoding fails.
    """
    # Try Google Geocoding first
    if settings.google_places_api_key:
        params = {
            "address": address,
            "key": settings.google_places_api_key,
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.get(GEOCODE_URL, params=params)
                response.raise_for_status()
                data = response.json()

                if data.get("status") == "OK" and data.get("results"):
                    location = data["results"][0]["geometry"]["location"]
                    return (location["lat"], location["lng"])
                else:
                    logger.warning("Google Geocoding failed (status=%s)", data.get("status"))
            except Exception:
                logger.exception("Google Geocoding error")

    # Fallback to Census Geocoder (free, no API key needed)
    logger.debug("Falling back to Census Geocoder")
    census_url = "https://geocoding.geo.census.gov/geocoder/locations/onelineaddress"
    params = {
        "address": address,
        "benchmark": "Public_AR_Current",
        "format": "json",
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.get(census_url, params=params)
            response.raise_for_status()
            data = response.json()

            matches = data.get("result", {}).get("addressMatches", [])
            if matches:
                coords = matches[0].get("coordinates", {})
                lat = coords.get("y")
                lng = coords.get("x")
                if lat and lng:
                    return (lat, lng)

            logger.debug("Census Geocoding: no matches found")
            return None

        except Exception:
            logger.exception("Census Geocoding error")
            return None


async def search_nearby_businesses(
    latitude: float,
    longitude: float,
    radius_meters: int = 1000,
    place_type: str | None = None,
) -> list[Business]:
    """
    Search for businesses near a location using Google Places API (Legacy).

    Args:
        latitude: Center point latitude
        longitude: Center point longitude
        radius_meters: Search radius in meters (default 1000m = ~0.6 miles)
        place_type: Single place type to filter by (optional)

    Returns:
        List of Business objects
    """
    if not settings.google_places_api_key:
        return []

    params: dict[str, Any] = {
        "location": f"{latitude},{longitude}",
        "radius": radius_meters,
        "key": settings.google_places_api_key,
    }

    if place_type:
        params["type"] = place_type

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            businesses = []
            page_count = 0
            max_pages = 3  # Google allows up to 3 pages (60 results)

            while page_count < max_pages:
                response = await client.get(PLACES_NEARBY_URL, params=params)
                response.raise_for_status()
                data = response.json()

                if data.get("status") not in ["OK", "ZERO_RESULTS"]:
                    logger.warning("Places API error (status=%s)", data.get("status"))
                    break

                for place in data.get("results", []):
                    # Filter out closed businesses
                    status = place.get("business_status", "OPERATIONAL")
                    if status in ("CLOSED_PERMANENTLY", "CLOSED_TEMPORARILY"):
                        logger.debug("Filtered closed business: %s (status=%s)", place.get("name"), status)
                        continue

                    name = place.get("name", "Unknown")

                    # Filter known-defunct businesses
                    if _is_defunct_business(name):
                        logger.debug("Filtered defunct business: %s", name)
                        continue

                    types = place.get("types", [])
                    business = Business(
                        name=name,
                        address=place.get("vicinity", ""),
                        category=_categorize_business(types),
                        types=types,
                        rating=place.get("rating"),
                        user_ratings_total=place.get("user_ratings_total"),
                        price_level=place.get("price_level"),
                        is_open=place.get("opening_hours", {}).get("open_now"),
                        phone=None,  # Not available in nearby search
                        website=None,  # Not available in nearby search
                        place_id=place.get("place_id"),
                        business_status=status,
                    )
                    businesses.append(business)

                # Follow pagination if available
                next_page_token = data.get("next_page_token")
                if not next_page_token:
                    break

                page_count += 1
                # Google requires a short delay before the next_page_token becomes valid
                await asyncio.sleep(2)
                params = {
                    "pagetoken": next_page_token,
                    "key": settings.google_places_api_key,
                }

            return businesses

        except Exception:
            logger.exception("Places API error")
            return []


async def search_businesses_by_text(
    query: str,
    location_bias_lat: float | None = None,
    location_bias_lng: float | None = None,
) -> list[Business]:
    """
    Search for businesses using a text query (Legacy API).

    Args:
        query: Search query (e.g., "restaurants in Weston CT")
        location_bias_lat: Optional latitude to bias results
        location_bias_lng: Optional longitude to bias results

    Returns:
        List of Business objects
    """
    if not settings.google_places_api_key:
        return []

    params: dict[str, Any] = {
        "query": query,
        "key": settings.google_places_api_key,
    }

    if location_bias_lat and location_bias_lng:
        params["location"] = f"{location_bias_lat},{location_bias_lng}"
        params["radius"] = 5000  # 5km bias radius

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.get(PLACES_TEXT_SEARCH_URL, params=params)
            response.raise_for_status()
            data = response.json()

            if data.get("status") not in ["OK", "ZERO_RESULTS"]:
                logger.warning("Places API error (status=%s)", data.get("status"))
                return []

            businesses = []
            for place in data.get("results", []):
                # Filter out closed businesses
                status = place.get("business_status", "OPERATIONAL")
                if status in ("CLOSED_PERMANENTLY", "CLOSED_TEMPORARILY"):
                    logger.debug("Filtered closed business (text): %s (status=%s)", place.get("name"), status)
                    continue

                name = place.get("name", "Unknown")

                # Filter known-defunct businesses
                if _is_defunct_business(name):
                    logger.debug("Filtered defunct business (text): %s", name)
                    continue

                types = place.get("types", [])
                business = Business(
                    name=name,
                    address=place.get("formatted_address", ""),
                    category=_categorize_business(types),
                    types=types,
                    rating=place.get("rating"),
                    user_ratings_total=place.get("user_ratings_total"),
                    price_level=place.get("price_level"),
                    is_open=place.get("opening_hours", {}).get("open_now"),
                    phone=None,
                    website=None,
                    place_id=place.get("place_id"),
                    business_status=status,
                )
                businesses.append(business)

            return businesses

        except Exception:
            logger.exception("Places API text search error")
            return []


async def get_area_businesses(
    address: str,
    radius_meters: int | None = None,
    radius_miles: float | None = None,
) -> LocationData | None:
    """
    Get all businesses in an area around an address.

    This is the main entry point for the Tenant Roster Agent.

    Args:
        address: Address to search around
        radius_meters: Search radius in meters (legacy parameter)
        radius_miles: Search radius in miles (preferred — converted to meters internally)

    If both are None, defaults to 3 miles (~4828m).
    If radius_miles is provided, it takes precedence over radius_meters.

    Returns:
        LocationData with all businesses found, or None if geocoding fails
    """
    # Resolve radius: prefer miles, fall back to meters, default to 3 miles
    if radius_miles is not None:
        effective_radius = miles_to_meters(radius_miles)
    elif radius_meters is not None:
        effective_radius = radius_meters
    else:
        effective_radius = miles_to_meters(3.0)  # default 3-mile trade area

    logger.info(
        "[places] Searching businesses around '%s' with radius=%dm (%.1f miles)",
        address, effective_radius, effective_radius / METERS_PER_MILE,
    )

    # First, try the improved location resolver for better parsing
    coords = None
    try:
        resolved = await resolve_location(address)
        if resolved.has_coordinates():
            coords = (resolved.latitude, resolved.longitude)
    except Exception:
        logger.debug("Location resolver failed, falling back to geocode_address")

    # Fall back to direct geocoding
    if not coords:
        coords = await geocode_address(address)
    if not coords:
        return None

    lat, lng = coords
    logger.debug("[places] Search center: lat=%.6f, lng=%.6f", lat, lng)

    # Search for different types of businesses
    # Legacy API only supports one type per request
    all_businesses: list[Business] = []
    seen_place_ids: set[str] = set()

    # Key business types to search for
    business_types = [
        # Retail
        "store",
        "shopping_mall",
        "clothing_store",
        "grocery_or_supermarket",
        "supermarket",
        "department_store",
        "convenience_store",
        "pharmacy",
        "hardware_store",
        "furniture_store",
        "electronics_store",
        "book_store",
        "pet_store",
        "home_goods_store",
        "shoe_store",
        "jewelry_store",
        # Dining
        "restaurant",
        "cafe",
        "bakery",
        "bar",
        "meal_takeaway",
        "meal_delivery",
        # Services
        "bank",
        "gym",
        "hair_care",
        "beauty_salon",
        "spa",
        "real_estate_agency",
        "doctor",
        "dentist",
        "laundry",
        "car_wash",
        "gas_station",
        "veterinary_care",
    ]

    for place_type in business_types:
        businesses = await search_nearby_businesses(lat, lng, effective_radius, place_type)
        for biz in businesses:
            if biz.place_id and biz.place_id not in seen_place_ids:
                seen_place_ids.add(biz.place_id)
                all_businesses.append(biz)

    # Also do a general nearby search to catch anything we missed
    general_businesses = await search_nearby_businesses(lat, lng, effective_radius, None)
    for biz in general_businesses:
        if biz.place_id and biz.place_id not in seen_place_ids:
            seen_place_ids.add(biz.place_id)
            all_businesses.append(biz)

    return LocationData(
        address=address,
        latitude=lat,
        longitude=lng,
        businesses=all_businesses,
        total_found=len(all_businesses),
    )


def format_tenant_report(location_data: LocationData) -> str:
    """
    Format business data into a report for the AI agent.

    Args:
        location_data: LocationData with businesses

    Returns:
        Formatted markdown report
    """
    if not location_data.businesses:
        return f"""**Business Search Results for {location_data.address}**

No businesses found within the search radius. This could mean:
- The area is primarily residential
- The search radius may need to be expanded
- The location may not have commercial development

*Note: This search covers approximately 1 mile radius from the specified location.*"""

    # Group businesses by category
    by_category: dict[str, list[Business]] = {}
    for biz in location_data.businesses:
        cat = biz.category
        if cat not in by_category:
            by_category[cat] = []
        by_category[cat].append(biz)

    # Sort categories
    sorted_categories = sorted(by_category.keys())

    lines = [
        f"**Business/Tenant Roster for {location_data.address}**",
        f"*Found {location_data.total_found} businesses within ~1 mile radius*\n",
    ]

    for category in sorted_categories:
        businesses = by_category[category]
        lines.append(f"**{category}** ({len(businesses)})")

        # Sort by rating (highest first)
        sorted_biz = sorted(
            businesses,
            key=lambda b: (b.rating or 0, b.user_ratings_total or 0),
            reverse=True
        )

        for biz in sorted_biz[:10]:  # Limit to top 10 per category
            rating_str = f"★{biz.rating:.1f}" if biz.rating else ""
            reviews_str = f"({biz.user_ratings_total} reviews)" if biz.user_ratings_total else ""
            lines.append(f"- {biz.name} {rating_str} {reviews_str}".strip())

        if len(businesses) > 10:
            lines.append(f"  *...and {len(businesses) - 10} more*")
        lines.append("")

    # Summary statistics
    dining_count = sum(1 for b in location_data.businesses if "Dining" in b.category)
    retail_count = sum(1 for b in location_data.businesses if "Retail" in b.category)
    services_count = sum(1 for b in location_data.businesses if "Services" in b.category)

    lines.append("---")
    lines.append("**Summary:**")
    lines.append(f"- Total Businesses: {location_data.total_found}")
    lines.append(f"- Dining/Food: {dining_count}")
    lines.append(f"- Retail: {retail_count}")
    lines.append(f"- Services: {services_count}")

    # Calculate average rating
    rated_businesses = [b for b in location_data.businesses if b.rating]
    if rated_businesses:
        avg_rating = sum(b.rating for b in rated_businesses) / len(rated_businesses)
        lines.append(f"- Average Rating: ★{avg_rating:.1f} (avg. Google rating across {len(rated_businesses)} businesses)")

    lines.append("\n*Source: Google Places API*")

    return "\n".join(lines)


async def analyze_tenant_roster(address: str, radius_miles: float = 3.0) -> str:
    """
    Main entry point for tenant roster analysis.

    Args:
        address: Address or location to analyze
        radius_miles: Trade area radius in miles

    Returns:
        Formatted tenant roster report
    """
    location_data = await get_area_businesses(address, radius_miles=radius_miles)

    if not location_data:
        # Try to get suggestions from location resolver
        try:
            resolved = await resolve_location(address)
            if resolved.suggestion_message:
                return f"Unable to find location: {address}. {resolved.suggestion_message}"
        except Exception:
            pass
        return f"Unable to find location: {address}. Please provide a valid address with city and state."

    return format_tenant_report(location_data)


async def get_tenants_structured(address: str, radius_miles: float = 3.0) -> list[dict] | None:
    """
    Get tenant data as structured list for use by other agents (e.g., void analysis).

    Args:
        address: Address to search around
        radius_miles: Trade area radius in miles

    Returns:
        List of tenant dicts with name, category, or None if geocoding fails
    """
    location_data = await get_area_businesses(address, radius_miles=radius_miles)

    if not location_data:
        return None

    tenants = []
    for biz in location_data.businesses:
        tenants.append({
            "name": biz.name,
            "category": biz.category,
            "rating": biz.rating,
            "reviews": biz.user_ratings_total,
            "types": biz.types[:3] if biz.types else [],  # First 3 types
        })

    return tenants


async def resolve_business_to_address(query: str) -> tuple[str, str] | None:
    """
    Resolve a business name query to a formatted street address.

    This is useful for queries like "GG and Joes in Westport" or
    "Starbucks near downtown Fairfield".

    Args:
        query: Business name with location context (e.g., "GG and Joes Westport CT")

    Returns:
        Tuple of (business_name, formatted_address) or None if not found
    """
    if not settings.google_places_api_key:
        logger.warning("Google Places API key not configured")
        return None

    # Search for the business using text search
    businesses = await search_businesses_by_text(query)

    if not businesses:
        logger.debug("No business found for query")
        return None

    # Return the first (most relevant) result
    best_match = businesses[0]
    logger.debug("Resolved business query to address")

    return (best_match.name, best_match.address)


def extract_business_query_from_message(message: str) -> str | None:
    """
    Extract a potential business name + location from a user message.

    Looks for patterns like:
    - "near/by/at [business name]"
    - "[business name] in/at [location]"
    - "downtown [location]"

    Args:
        message: User's message

    Returns:
        Extracted query string suitable for Places API, or None
    """
    import re

    message_lower = message.lower()

    # Skip if message contains explicit addresses (has numbers + street keywords)
    street_keywords = ["st", "street", "ave", "avenue", "rd", "road", "blvd",
                       "boulevard", "drive", "dr", "way", "lane", "ln"]
    has_street = any(kw in message_lower for kw in street_keywords)
    has_numbers = bool(re.search(r'\d{2,}', message))  # 2+ digit numbers

    if has_street and has_numbers:
        # This is likely already an address
        return None

    # Patterns to extract business + location queries
    patterns = [
        # "by/near/at [business] in [location]"
        r'(?:by|near|at|around)\s+([a-zA-Z0-9\s&\'\-]+?)(?:\s+in\s+|\s+at\s+)([a-zA-Z\s]+)',
        # "in downtown [location] by [business]"
        r'(?:in\s+)?downtown\s+([a-zA-Z\s]+?)(?:\s+by|\s+near|\s+at)\s+([a-zA-Z0-9\s&\'\-]+)',
        # "[business] in [location]"
        r'([a-zA-Z0-9\s&\'\-]{3,}?)\s+in\s+([a-zA-Z\s]+?)(?:\?|$|\.)',
    ]

    for pattern in patterns:
        match = re.search(pattern, message, re.IGNORECASE)
        if match:
            groups = match.groups()
            # Combine matched groups into a search query
            query_parts = [g.strip() for g in groups if g and g.strip()]
            if query_parts:
                return " ".join(query_parts)

    # Check for "downtown [location]" without business name
    downtown_match = re.search(r'downtown\s+([a-zA-Z\s]+?)(?:\?|$|\.|\s+(?:foot|traffic))',
                                message, re.IGNORECASE)
    if downtown_match:
        location = downtown_match.group(1).strip()
        return f"downtown {location}"

    return None
