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
from app.services.user_llm import ResolvedLLM

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


def affordability_tier(median_income: int | float | None) -> dict:
    """Classify a trade area's affordability from median household income.

    Used to scrub brand suggestions to the right price tier (e.g. don't pitch a
    luxury concept into a value trade area). Pure + deterministic so it can be
    unit-tested without an LLM.
    """
    if not median_income or median_income <= 0:
        return {"key": "unknown", "label": "an income-unknown"}
    if median_income < 50_000:
        return {"key": "value", "label": "a value (lower-income)"}
    if median_income < 90_000:
        return {"key": "moderate", "label": "a moderate-income"}
    if median_income < 150_000:
        return {"key": "affluent", "label": "an affluent"}
    return {"key": "luxury", "label": "a luxury (high-income)"}


# Static prompt fragments (kept out of the f-string so the JSON braces below
# don't need escaping).
_VOID_CAVEAT = """IMPORTANT DATA CAVEAT: The existing tenant list comes from Google Places API and may NOT be exhaustive. Google Places can miss businesses, especially in dense markets. When identifying voids:
- Use cautious language like "no [category] found in our data" rather than absolute claims like "there is no [business]"
- If a common national chain (e.g., Chipotle, Panera, LA Fitness, Crunch) is not in the tenant list, note that it "was not found in our search data" rather than definitively stating it is absent from the market
- Focus on categories that are clearly underserved relative to the demographics, rather than claiming specific brands don't exist
- When suggesting brands, note whether similar concepts already appear in the data"""

_VOID_JSON_SCHEMA = """For each void opportunity:
1. Assess the demographic fit (is there demand?)
2. Check existing competition (is the category underserved?)
3. Consider co-tenancy (what existing tenants would complement?)
4. Score the opportunity (0-100 match score)
5. Suggest specific tenant brands appropriate for this trade area's price tier

Return a JSON object with this structure:
{
    "property_summary": "Brief summary of the property and trade area",
    "demographic_tier": "value | moderate | affluent | luxury | unknown",
    "analysis_parameters": {
        "address": "Address analyzed",
        "radius_miles": 3.0,
        "use_case": "leasing"
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
    "excluded_suggestions": [
        {"tenant": "Brand name", "reason": "Too premium for this value trade area"}
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

_LEASING_LENS = (
    "You are supporting LEASING. The reader is filling vacant space and will reach "
    "out to tenants. Emphasize concrete, recruitable targets: named brands that are "
    "actively expanding, co-tenancy logic, and who to pursue first. Make it "
    "actionable for outreach."
)

_INVESTMENT_LENS = (
    "You are supporting an INVESTMENT MEMO. The reader is underwriting an "
    "acquisition, not filling a suite. Frame each void as a demand signal and a "
    "risk/return consideration: how deep and durable the unmet demand is, what it "
    "implies for achievable rents / NOI / downside, and how confident the read is "
    "given the data. De-emphasize specific brands to recruit; emphasize the "
    "category-level thesis and the risks."
)


async def analyze_voids_for_property(
    address: str,
    existing_tenants: list[dict] | None = None,
    demographics: dict | None = None,
    radius_miles: float = 3.0,
    use_case: str = "leasing",
    tenant_focus: str = "",
    resolved_llm: ResolvedLLM | None = None,
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

    income = demographics.get("median_income") if demographics else None
    tier = affordability_tier(income)
    use_case = (use_case or "leasing").lower()
    if use_case not in ("leasing", "investment_memo"):
        use_case = "leasing"
    lens = _INVESTMENT_LENS if use_case == "investment_memo" else _LEASING_LENS

    income_str = f"${income:,}" if income else "unknown"
    scrub_clause = (
        "\n\nDEMOGRAPHIC SCRUBBING (required): This is "
        f"{tier['label']} trade area (median household income {income_str}). "
        "Match every suggested brand's price tier to the trade area. Do NOT pitch "
        "luxury/premium concepts into a value or moderate area, and do NOT pitch "
        "deep-discount concepts into an affluent/luxury area. That is the single "
        "most common way these lists go wrong (e.g. Neiman Marcus in a low-income "
        "trade area). For any brand you would naturally list but exclude on these "
        "grounds, add it to `excluded_suggestions` with a one-line reason so the "
        "user can see what was filtered and override if they disagree."
    )
    focus_clause = ""
    if tenant_focus and tenant_focus.strip():
        focus_clause = (
            "\n\nTENANT FOCUS: The user is specifically interested in: "
            f"{tenant_focus.strip()}. Lead with categories/brands matching this focus "
            "(type and/or size); you may note one or two adjacent opportunities, "
            "but keep the focus front and center."
        )

    system_prompt = (
        f"You are a commercial real estate void/gap analyst. {lens}\n\n"
        f"{_VOID_CAVEAT}{scrub_clause}{focus_clause}\n\n{_VOID_JSON_SCHEMA}"
    )

    llm = resolved_llm.client if resolved_llm else get_llm_client()
    model = resolved_llm.model if resolved_llm else (settings.llm_model or settings.anthropic_model)
    response = await llm.chat(
        LLMChatRequest(
            model=model,
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
    use_case: str = "leasing",
    tenant_focus: str = "",
    resolved_llm: ResolvedLLM | None = None,
) -> str:
    """
    Generate a formatted void analysis report as text.

    ``use_case`` is "leasing" (recruitable targets) or "investment_memo" (gaps as
    acquisition demand signals). ``tenant_focus`` narrows to specific tenant
    types/sizes. Returns a human-readable report string.
    """
    analysis = await analyze_voids_for_property(
        address=property_address,
        existing_tenants=existing_tenants,
        demographics=demographics,
        radius_miles=radius_miles,
        use_case=use_case,
        tenant_focus=tenant_focus,
        resolved_llm=resolved_llm,
    )

    if "error" in analysis:
        return f"Error generating void analysis: {analysis['error']}"

    # Format as readable report
    title = (
        "Investment-Memo Void Analysis"
        if use_case == "investment_memo"
        else "Void Analysis Report"
    )
    lines = []
    lines.append(f"**{title}**")
    lines.append(f"*{property_address}*")
    lines.append(f"Trade Area: {radius_miles}-mile radius")
    if tenant_focus and tenant_focus.strip():
        lines.append(f"Focus: {tenant_focus.strip()}")
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

    # Demographic-mismatch suggestions the model filtered out (transparency,
    # so the user can override if they disagree with a scrub).
    excluded = analysis.get("excluded_suggestions") or []
    if excluded:
        lines.append("**Filtered out (demographic mismatch):**")
        for item in excluded:
            tenant = item.get("tenant", "?")
            reason = item.get("reason", "")
            line = f"- {tenant}"
            if reason:
                line += f": {reason}"
            lines.append(line)
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
