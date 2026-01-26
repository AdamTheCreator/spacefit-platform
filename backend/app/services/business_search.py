"""
Business Search Service

Multi-source business search with cross-validation.
Currently supports Google Places, with Yellow Pages integration planned.

This service provides high-accuracy business data by:
1. Querying multiple data sources in parallel
2. Cross-referencing results for validation
3. Providing confidence scores based on source agreement
"""

from dataclasses import dataclass, field
from typing import Any
from app.services.places import (
    search_businesses_by_text,
    search_nearby_businesses,
    geocode_address,
    Business,
)


@dataclass
class BusinessSearchResult:
    """A validated business search result with source attribution."""
    name: str
    address: str
    category: str
    rating: float | None = None
    reviews_count: int | None = None
    phone: str | None = None
    website: str | None = None
    sources: list[str] = field(default_factory=list)
    confidence: float = 1.0  # 0-1 score based on source agreement
    place_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "address": self.address,
            "category": self.category,
            "rating": self.rating,
            "reviews_count": self.reviews_count,
            "phone": self.phone,
            "website": self.website,
            "sources": self.sources,
            "confidence": self.confidence,
        }


@dataclass
class BusinessSearchResponse:
    """Response from a business search query."""
    query: str
    location: str
    total_results: int
    results: list[BusinessSearchResult]
    sources_used: list[str]
    warnings: list[str] = field(default_factory=list)

    def to_formatted_report(self) -> str:
        """Format the search results as a readable report."""
        if not self.results:
            return f"""**Business Search Results**

No businesses found matching your search for "{self.query}" in {self.location}.

This could mean:
- The search terms may need adjustment
- The area may not have businesses of this type
- Try expanding the search radius

*Sources checked: {', '.join(self.sources_used)}*"""

        lines = [
            f"**Business Search Results: {self.query}**",
            f"*Location: {self.location} | Found: {self.total_results} businesses*\n",
        ]

        # Group by category
        by_category: dict[str, list[BusinessSearchResult]] = {}
        for biz in self.results:
            cat = biz.category
            if cat not in by_category:
                by_category[cat] = []
            by_category[cat].append(biz)

        for category in sorted(by_category.keys()):
            businesses = by_category[category]
            lines.append(f"**{category}** ({len(businesses)})")

            for biz in sorted(businesses, key=lambda b: (b.rating or 0), reverse=True)[:10]:
                rating_str = f"★{biz.rating:.1f}" if biz.rating else ""
                reviews_str = f"({biz.reviews_count} reviews)" if biz.reviews_count else ""
                lines.append(f"- **{biz.name}** {rating_str} {reviews_str}")
                lines.append(f"  {biz.address}")

            if len(businesses) > 10:
                lines.append(f"  *...and {len(businesses) - 10} more*")
            lines.append("")

        # Add warnings if any
        if self.warnings:
            lines.append("---")
            lines.append("**Notes:**")
            for warning in self.warnings:
                lines.append(f"- {warning}")

        lines.append("")
        lines.append(f"*Sources: {', '.join(self.sources_used)}*")

        return "\n".join(lines)


async def search_businesses(
    query: str | None = None,
    business_type: str | None = None,
    location: str | None = None,
    radius_miles: float = 2.0,
) -> BusinessSearchResponse:
    """
    Search for businesses using multiple data sources.

    Args:
        query: Full search query (e.g., "coffee shops Westport CT")
        business_type: Type of business (e.g., "coffee shop")
        location: Location to search in (e.g., "Westport, CT")
        radius_miles: Search radius in miles

    Returns:
        BusinessSearchResponse with validated results from all sources
    """
    warnings: list[str] = []
    sources_used: list[str] = []

    # Build the search query
    if query:
        search_query = query
    elif business_type and location:
        search_query = f"{business_type} {location}"
    elif location:
        search_query = f"businesses in {location}"
    else:
        return BusinessSearchResponse(
            query=query or "",
            location=location or "Unknown",
            total_results=0,
            results=[],
            sources_used=[],
            warnings=["No search query or location provided"],
        )

    display_location = location or search_query

    # === Source 1: Google Places API ===
    google_results: list[BusinessSearchResult] = []

    try:
        # Try text search first (more flexible)
        places = await search_businesses_by_text(search_query)

        if places:
            sources_used.append("Google Places")
            for place in places:
                google_results.append(BusinessSearchResult(
                    name=place.name,
                    address=place.address,
                    category=place.category,
                    rating=place.rating,
                    reviews_count=place.user_ratings_total,
                    phone=place.phone,
                    website=place.website,
                    sources=["Google Places"],
                    confidence=0.9,  # High confidence for Google
                    place_id=place.place_id,
                ))

        # If text search returned few results, also try nearby search
        if len(places) < 5 and location:
            coords = await geocode_address(location)
            if coords:
                lat, lng = coords
                radius_meters = int(radius_miles * 1609.34)  # Convert miles to meters

                # Determine place type from business_type
                place_type = _get_google_place_type(business_type) if business_type else "cafe"

                nearby = await search_nearby_businesses(lat, lng, radius_meters, place_type)
                for place in nearby:
                    # Avoid duplicates
                    if not any(r.place_id == place.place_id for r in google_results if r.place_id):
                        google_results.append(BusinessSearchResult(
                            name=place.name,
                            address=place.address,
                            category=place.category,
                            rating=place.rating,
                            reviews_count=place.user_ratings_total,
                            sources=["Google Places"],
                            confidence=0.9,
                            place_id=place.place_id,
                        ))

    except Exception as e:
        warnings.append(f"Google Places search encountered an issue: {str(e)}")

    # === Source 2: Yellow Pages API (TODO - placeholder for future) ===
    # yellow_pages_results = await search_yellow_pages(search_query, location)
    # if yellow_pages_results:
    #     sources_used.append("Yellow Pages")

    # === Cross-reference and merge results ===
    # For now, just use Google results
    # When Yellow Pages is added, we'll merge and validate
    all_results = google_results

    # Sort by rating (highest first)
    all_results.sort(key=lambda r: (r.rating or 0, r.reviews_count or 0), reverse=True)

    return BusinessSearchResponse(
        query=search_query,
        location=display_location,
        total_results=len(all_results),
        results=all_results,
        sources_used=sources_used if sources_used else ["No sources available"],
        warnings=warnings,
    )


def _get_google_place_type(business_type: str) -> str:
    """Map common business type descriptions to Google Place types."""
    type_lower = business_type.lower()

    mapping = {
        "coffee": "cafe",
        "coffee shop": "cafe",
        "cafe": "cafe",
        "restaurant": "restaurant",
        "food": "restaurant",
        "dining": "restaurant",
        "gym": "gym",
        "fitness": "gym",
        "bank": "bank",
        "salon": "hair_care",
        "hair": "hair_care",
        "spa": "spa",
        "hotel": "lodging",
        "gas": "gas_station",
        "grocery": "supermarket",
        "supermarket": "supermarket",
        "pharmacy": "pharmacy",
        "doctor": "doctor",
        "dentist": "dentist",
        "bar": "bar",
        "store": "store",
        "shop": "store",
    }

    for key, value in mapping.items():
        if key in type_lower:
            return value

    return "establishment"  # Generic fallback


# === Future: Yellow Pages Integration ===

async def search_yellow_pages(query: str, location: str) -> list[BusinessSearchResult]:
    """
    Search Yellow Pages for businesses.

    TODO: Implement Yellow Pages API integration.
    This will provide a second data source for cross-validation.

    API options:
    - YP.com API (if available)
    - Data.com
    - InfoUSA
    - Web scraping as fallback
    """
    # Placeholder for future implementation
    return []


async def cross_reference_results(
    google_results: list[BusinessSearchResult],
    yellow_pages_results: list[BusinessSearchResult],
) -> list[BusinessSearchResult]:
    """
    Cross-reference results from multiple sources.

    Matching logic:
    1. Exact name + address match -> confidence 1.0
    2. Fuzzy name match + same address -> confidence 0.95
    3. Same address, different name -> flag for review
    4. Only in one source -> confidence based on that source

    TODO: Implement when Yellow Pages is added.
    """
    # Placeholder for future implementation
    return google_results
