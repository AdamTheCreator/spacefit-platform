"""
Void Analysis Agent

Generates comprehensive void/gap analyses for commercial properties.
Identifies missing tenant categories based on:
- Demographics data
- Existing tenant roster
- Trade area analysis
- Market benchmarks
"""

import json

from app.core.config import settings
from app.llm import LLMChatMessage, LLMChatRequest, get_llm_client

# Define retail categories and typical co-tenancy patterns
RETAIL_CATEGORIES = {
    "grocery": {
        "name": "Grocery",
        "subcategories": ["Conventional", "Discount", "Specialty/Ethnic", "Natural/Organic"],
        "typical_sf_range": (25000, 65000),
        "trade_area_miles": 3,
        "key_demographics": ["population", "households", "income"],
        "common_cotenants": ["pharmacy", "bank", "quick_service"],
    },
    "fast_casual": {
        "name": "Fast Casual Dining",
        "subcategories": ["Mexican", "Mediterranean", "Asian", "American", "Healthy/Bowls"],
        "typical_sf_range": (1800, 3500),
        "trade_area_miles": 3,
        "key_demographics": ["population", "daytime_employment", "income"],
        "common_cotenants": ["coffee", "retail", "fitness"],
    },
    "quick_service": {
        "name": "Quick Service Restaurants",
        "subcategories": ["Burgers", "Chicken", "Pizza", "Subs/Sandwiches", "Coffee/Donuts"],
        "typical_sf_range": (1500, 3000),
        "trade_area_miles": 2,
        "key_demographics": ["traffic_count", "population", "households"],
        "common_cotenants": ["gas", "convenience", "drive_thru"],
    },
    "fitness": {
        "name": "Fitness",
        "subcategories": ["Traditional Gym", "Boutique Fitness", "Yoga/Pilates", "Martial Arts"],
        "typical_sf_range": (2000, 45000),
        "trade_area_miles": 5,
        "key_demographics": ["population", "income", "age_25_44"],
        "common_cotenants": ["fast_casual", "smoothie", "athleisure"],
    },
    "medical": {
        "name": "Medical/Healthcare",
        "subcategories": ["Urgent Care", "Dental", "Vision", "Physical Therapy", "Med Spa"],
        "typical_sf_range": (1500, 5000),
        "trade_area_miles": 5,
        "key_demographics": ["population", "households", "age_55_plus"],
        "common_cotenants": ["pharmacy", "lab_services", "senior_services"],
    },
    "personal_services": {
        "name": "Personal Services",
        "subcategories": ["Hair Salon", "Nail Salon", "Barbershop", "Spa/Massage", "Waxing"],
        "typical_sf_range": (1000, 2500),
        "trade_area_miles": 3,
        "key_demographics": ["population", "income", "households"],
        "common_cotenants": ["retail", "dining", "fitness"],
    },
    "pet": {
        "name": "Pet Services",
        "subcategories": ["Pet Supplies", "Grooming", "Veterinary", "Daycare/Boarding"],
        "typical_sf_range": (2000, 15000),
        "trade_area_miles": 5,
        "key_demographics": ["households", "income", "homeownership"],
        "common_cotenants": ["grocery", "home_improvement", "retail"],
    },
    "coffee": {
        "name": "Coffee/Beverage",
        "subcategories": ["National Chain", "Regional Chain", "Local/Specialty", "Bubble Tea"],
        "typical_sf_range": (1200, 2500),
        "trade_area_miles": 2,
        "key_demographics": ["traffic_count", "daytime_employment", "income"],
        "common_cotenants": ["office", "retail", "fast_casual"],
    },
    "kids_entertainment": {
        "name": "Kids Entertainment/Education",
        "subcategories": ["Tutoring", "Dance/Gymnastics", "Party Venues", "Indoor Play"],
        "typical_sf_range": (2000, 8000),
        "trade_area_miles": 5,
        "key_demographics": ["households", "age_under_18", "income"],
        "common_cotenants": ["family_dining", "pediatric", "retail"],
    },
    "financial": {
        "name": "Financial Services",
        "subcategories": ["Bank", "Credit Union", "Insurance", "Tax Prep", "Wealth Management"],
        "typical_sf_range": (1500, 4000),
        "trade_area_miles": 5,
        "key_demographics": ["population", "income", "employment"],
        "common_cotenants": ["professional_services", "retail", "dining"],
    },
}

# Example brands by category for suggestions
BRAND_SUGGESTIONS = {
    "fast_casual": {
        "Mexican": ["Chipotle", "Qdoba", "Moe's Southwest", "Taco Bell Cantina"],
        "Mediterranean": ["Cava", "Naf Naf Grill", "Roti", "Zoe's Kitchen"],
        "Asian": ["Panda Express", "Teriyaki Madness", "Pei Wei", "Waba Grill"],
        "American": ["Five Guys", "Shake Shack", "Smashburger", "The Habit"],
        "Healthy/Bowls": ["Sweetgreen", "CAVA", "Just Salad", "Freshii"],
    },
    "fitness": {
        "Boutique Fitness": ["Orangetheory", "F45", "Barry's", "SoulCycle", "Pure Barre"],
        "Traditional Gym": ["Planet Fitness", "LA Fitness", "Crunch", "EōS Fitness"],
        "Yoga/Pilates": ["CorePower Yoga", "Club Pilates", "YogaWorks", "Stretch Zone"],
    },
    "medical": {
        "Urgent Care": ["CityMD", "GoHealth", "MedExpress", "Concentra"],
        "Dental": ["Aspen Dental", "Heartland Dental", "Pacific Dental"],
        "Vision": ["Warby Parker", "LensCrafters", "Visionworks"],
    },
    "coffee": {
        "National Chain": ["Starbucks", "Dunkin'", "Dutch Bros"],
        "Regional Chain": ["Philz Coffee", "Blue Bottle", "Intelligentsia"],
    },
    "pet": {
        "Pet Supplies": ["PetSmart", "Petco", "Pet Supplies Plus"],
        "Grooming": ["PetSmart Grooming", "Petco Grooming", "Scenthound"],
    },
}


async def analyze_voids_for_property(
    address: str,
    existing_tenants: list[dict] | None = None,
    demographics: dict | None = None,
    radius_miles: float = 3.0,
) -> dict:
    """
    Generate a comprehensive void analysis for a property.

    Args:
        address: Property address
        existing_tenants: List of current tenants with name, category, and SF
        demographics: Demographics data for the trade area
        radius_miles: Trade area radius in miles

    Returns:
        dict with categories, voids, and recommendations
    """
    # Build context for Claude
    context_parts = []

    context_parts.append(f"Property Address: {address}")
    context_parts.append(f"Trade Area Radius: {radius_miles} miles")

    if existing_tenants:
        tenant_summary = []
        categories_present = set()
        for tenant in existing_tenants:
            name = tenant.get("name", "Unknown")
            category = tenant.get("category", "unknown")
            sf = tenant.get("square_footage")
            categories_present.add(category.lower())
            tenant_summary.append(f"- {name} ({category})" + (f" - {sf:,} SF" if sf else ""))
        context_parts.append(f"\nExisting Tenants ({len(existing_tenants)}):")
        context_parts.append("\n".join(tenant_summary))
        context_parts.append(f"\nCategories Present: {', '.join(sorted(categories_present))}")

    if demographics:
        demo_parts = []
        if demographics.get("population"):
            demo_parts.append(f"Population: {demographics['population']:,}")
        if demographics.get("households"):
            demo_parts.append(f"Households: {demographics['households']:,}")
        if demographics.get("median_income"):
            demo_parts.append(f"Median HH Income: ${demographics['median_income']:,}")
        if demographics.get("daytime_employment"):
            demo_parts.append(f"Daytime Employment: {demographics['daytime_employment']:,}")
        if demographics.get("traffic_count"):
            demo_parts.append(f"Traffic Count: {demographics['traffic_count']:,} VPD")
        if demo_parts:
            context_parts.append(f"\nTrade Area Demographics ({radius_miles}-mile):")
            context_parts.append("\n".join(demo_parts))

    # Add category reference
    category_ref = []
    for cat_id, cat_info in RETAIL_CATEGORIES.items():
        category_ref.append(f"- {cat_info['name']}: {', '.join(cat_info['subcategories'])}")
    context_parts.append("\nRetail Categories Reference:")
    context_parts.append("\n".join(category_ref))

    context = "\n".join(context_parts)

    system_prompt = """You are a commercial real estate void/gap analyst. Your job is to identify missing tenant categories at a retail property based on demographics and existing tenant mix.

For each void opportunity:
1. Assess the demographic fit (is there demand?)
2. Check existing competition (is the category underserved?)
3. Consider co-tenancy (what existing tenants would complement?)
4. Score the opportunity (0-100 match score)
5. Suggest specific tenant brands

Return a JSON object with this structure:
{
    "property_summary": "Brief summary of the property and trade area",
    "analysis_parameters": {
        "address": "Address analyzed",
        "radius_miles": 3.0,
        "date": "2025-01-11"
    },
    "categories": [
        {
            "category_name": "Fast Casual Mediterranean",
            "parent_category": "Fast Casual Dining",
            "is_void": true,
            "match_score": 89,
            "rationale": "Why this is a void/opportunity",
            "demographic_support": "Which demographics support this",
            "competitor_analysis": "Nearest competitor info",
            "suggested_tenants": ["Cava", "Naf Naf Grill"],
            "estimated_sf_need": 2200,
            "priority": "high"
        }
    ],
    "summary": {
        "total_voids": 5,
        "high_priority": ["Category names"],
        "medium_priority": ["Category names"],
        "well_served": ["Category names already present"],
        "key_recommendation": "Overall recommendation"
    }
}

Analyze comprehensively but return ONLY valid JSON."""

    llm = get_llm_client()
    response = await llm.chat(
        LLMChatRequest(
            model=settings.llm_model or settings.anthropic_model,
            max_tokens=4096,
            system=system_prompt,
            messages=[
                LLMChatMessage(
                    role="user",
                    content=(
                        "Analyze voids for this property:\n\n"
                        f"{context}\n\n"
                        "Provide comprehensive void analysis. Return JSON only."
                    ),
                )
            ],
        )
    )

    response_text = response.content.strip()

    # Parse JSON from response
    try:
        # Handle potential markdown code blocks
        if "```json" in response_text:
            response_text = response_text.split("```json")[1].split("```")[0]
        elif "```" in response_text:
            response_text = response_text.split("```")[1].split("```")[0]

        return json.loads(response_text)
    except json.JSONDecodeError:
        # Return structured error response
        return {
            "error": "Failed to parse void analysis",
            "raw_response": response_text[:500],
            "categories": [],
            "summary": {"total_voids": 0, "high_priority": []},
        }


async def generate_void_report(
    property_address: str,
    existing_tenants: list[dict] | None = None,
    demographics: dict | None = None,
    radius_miles: float = 3.0,
) -> str:
    """
    Generate a formatted void analysis report as text.

    Returns a human-readable report string.
    """
    analysis = await analyze_voids_for_property(
        address=property_address,
        existing_tenants=existing_tenants,
        demographics=demographics,
        radius_miles=radius_miles,
    )

    if "error" in analysis:
        return f"Error generating void analysis: {analysis['error']}"

    # Format as readable report
    lines = []
    lines.append(f"**Void Analysis Report**")
    lines.append(f"*{property_address}*")
    lines.append(f"Trade Area: {radius_miles}-mile radius")
    lines.append("")

    if analysis.get("property_summary"):
        lines.append(analysis["property_summary"])
        lines.append("")

    # High priority voids
    summary = analysis.get("summary", {})
    if summary.get("high_priority"):
        lines.append("**High Priority Opportunities:**")
        for cat in summary["high_priority"]:
            lines.append(f"- {cat}")
        lines.append("")

    # Category details
    categories = analysis.get("categories", [])
    if categories:
        lines.append("**Detailed Analysis:**")
        lines.append("")

        for cat in sorted(categories, key=lambda x: x.get("match_score", 0), reverse=True):
            if cat.get("is_void"):
                score = cat.get("match_score", 0)
                priority = cat.get("priority", "medium").upper()
                lines.append(f"**{cat['category_name']}** - {score}% Match ({priority} Priority)")

                if cat.get("rationale"):
                    lines.append(f"  *Why:* {cat['rationale']}")

                if cat.get("suggested_tenants"):
                    lines.append(f"  *Suggested:* {', '.join(cat['suggested_tenants'])}")

                if cat.get("estimated_sf_need"):
                    lines.append(f"  *Typical Size:* {cat['estimated_sf_need']:,} SF")

                lines.append("")

    # Well-served categories
    if summary.get("well_served"):
        lines.append("**Categories Well-Served:**")
        lines.append(", ".join(summary["well_served"]))
        lines.append("")

    # Key recommendation
    if summary.get("key_recommendation"):
        lines.append("**Key Recommendation:**")
        lines.append(summary["key_recommendation"])

    return "\n".join(lines)
