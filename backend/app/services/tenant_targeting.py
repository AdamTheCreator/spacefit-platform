"""
Tenant Targeting Service

Cross-references void analysis results with property demographics and traffic
data to score how well target tenants fit a specific property.
"""

import logging
from dataclasses import dataclass, field

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.models.deal import Property
from app.db.models.document import VoidAnalysisResult

logger = logging.getLogger(__name__)


@dataclass
class TenantFitResult:
    """Fit assessment for a single tenant at a specific property."""

    tenant_name: str
    fit_score: int  # 0-100
    reasons: list[str] = field(default_factory=list)
    demographics_match: bool = False
    traffic_match: bool = False
    co_tenancy_match: bool = False


# Minimum thresholds for tenant categories
TENANT_CATEGORY_REQUIREMENTS: dict[str, dict] = {
    "QSR": {
        "min_traffic_vpd": 20000,
        "min_population_3mi": 30000,
        "preferred_categories": ["dining", "food", "restaurant"],
    },
    "Fast Casual": {
        "min_traffic_vpd": 15000,
        "min_population_3mi": 25000,
        "min_hhi": 50000,
        "preferred_categories": ["dining", "food", "restaurant"],
    },
    "Coffee": {
        "min_traffic_vpd": 15000,
        "min_population_3mi": 20000,
        "preferred_categories": ["dining", "food", "coffee"],
    },
    "Fitness": {
        "min_traffic_vpd": 10000,
        "min_population_3mi": 30000,
        "preferred_categories": ["health", "fitness", "gym"],
    },
    "Medical": {
        "min_traffic_vpd": 8000,
        "min_population_3mi": 25000,
        "preferred_categories": ["health", "medical", "dental"],
    },
    "Retail": {
        "min_traffic_vpd": 15000,
        "min_population_3mi": 30000,
        "preferred_categories": ["retail", "shopping"],
    },
    "Service": {
        "min_traffic_vpd": 8000,
        "min_population_3mi": 15000,
        "preferred_categories": ["service", "salon", "barber"],
    },
}


def _classify_tenant(tenant_name: str) -> str | None:
    """
    Attempt to classify a tenant into a broad category based on name.

    Args:
        tenant_name: Name of the tenant.

    Returns:
        Category string or None if no match.
    """
    name_lower = tenant_name.lower()

    qsr_keywords = ["mcdonald", "burger", "taco bell", "wendy", "chick-fil-a", "popeye", "subway", "sonic"]
    if any(kw in name_lower for kw in qsr_keywords):
        return "QSR"

    fast_casual_keywords = ["chipotle", "panera", "wingstop", "panda express", "five guys", "shake shack"]
    if any(kw in name_lower for kw in fast_casual_keywords):
        return "Fast Casual"

    coffee_keywords = ["starbucks", "dunkin", "dutch bros", "coffee", "peet"]
    if any(kw in name_lower for kw in coffee_keywords):
        return "Coffee"

    fitness_keywords = ["planet fitness", "anytime fitness", "orangetheory", "gym", "fitness", "crossfit"]
    if any(kw in name_lower for kw in fitness_keywords):
        return "Fitness"

    medical_keywords = ["urgent care", "dental", "orthodont", "clinic", "medical", "health", "chiro"]
    if any(kw in name_lower for kw in medical_keywords):
        return "Medical"

    service_keywords = ["salon", "barber", "nails", "spa", "laundry", "cleaners", "tax"]
    if any(kw in name_lower for kw in service_keywords):
        return "Service"

    retail_keywords = ["dollar", "store", "shop", "mart", "boutique", "wireless", "mobile"]
    if any(kw in name_lower for kw in retail_keywords):
        return "Retail"

    return None


async def check_tenant_intersection_fit(
    property_id: str,
    target_tenants: list[str],
    db: AsyncSession,
) -> list[TenantFitResult]:
    """
    Cross-reference void analysis results with property demographics and
    traffic data to score how well each target tenant fits the property.

    For each target tenant, the scoring considers:
    - Demographics match (population, income vs. tenant requirements)
    - Traffic match (VPD vs. tenant minimum)
    - Co-tenancy match (are void categories aligned with tenant type?)

    Args:
        property_id: ID of the Property to evaluate.
        target_tenants: List of tenant names to check fit for.
        db: Async database session.

    Returns:
        List of TenantFitResult, one per target tenant, sorted by
        fit_score descending.
    """
    # Fetch property
    prop_result = await db.execute(
        select(Property).where(Property.id == property_id)
    )
    prop = prop_result.scalar_one_or_none()
    if not prop:
        logger.warning("[tenant_targeting] Property %s not found", property_id)
        return [
            TenantFitResult(
                tenant_name=t,
                fit_score=0,
                reasons=["Property not found"],
            )
            for t in target_tenants
        ]

    # Fetch void analysis results for this property
    void_result = await db.execute(
        select(VoidAnalysisResult)
        .where(VoidAnalysisResult.property_id == property_id)
        .order_by(VoidAnalysisResult.created_at.desc())
    )
    void_analysis = void_result.scalar_one_or_none()

    void_categories: set[str] = set()
    if void_analysis and void_analysis.results:
        for category in void_analysis.results.keys():
            void_categories.add(category.lower())

    results: list[TenantFitResult] = []

    for tenant_name in target_tenants:
        score = 0
        reasons: list[str] = []
        demographics_match = False
        traffic_match = False
        co_tenancy_match = False

        # Classify the tenant
        category = _classify_tenant(tenant_name)
        requirements = TENANT_CATEGORY_REQUIREMENTS.get(category or "", {})

        # --- Demographics scoring (up to 35 points) ---
        min_pop = requirements.get("min_population_3mi", 20000)
        min_hhi = requirements.get("min_hhi", 0)

        if prop.population_3mi:
            if prop.population_3mi >= min_pop:
                score += 20
                demographics_match = True
                reasons.append(
                    f"Population 3mi ({prop.population_3mi:,}) meets "
                    f"minimum ({min_pop:,})"
                )
            elif prop.population_3mi >= min_pop * 0.7:
                score += 10
                reasons.append(
                    f"Population 3mi ({prop.population_3mi:,}) is close to "
                    f"minimum ({min_pop:,})"
                )
            else:
                reasons.append(
                    f"Population 3mi ({prop.population_3mi:,}) below "
                    f"minimum ({min_pop:,})"
                )
        else:
            reasons.append("No population data available")

        if min_hhi and prop.median_hhi_3mi:
            if prop.median_hhi_3mi >= min_hhi:
                score += 15
                demographics_match = True
                reasons.append(
                    f"Median HHI (${prop.median_hhi_3mi:,.0f}) meets "
                    f"minimum (${min_hhi:,.0f})"
                )
            else:
                reasons.append(
                    f"Median HHI (${prop.median_hhi_3mi:,.0f}) below "
                    f"minimum (${min_hhi:,.0f})"
                )
        elif min_hhi:
            reasons.append("No income data available")

        # --- Traffic scoring (up to 30 points) ---
        min_traffic = requirements.get("min_traffic_vpd", 10000)

        if prop.traffic_count_vpd:
            if prop.traffic_count_vpd >= min_traffic:
                score += 30
                traffic_match = True
                reasons.append(
                    f"Traffic ({prop.traffic_count_vpd:,} VPD) meets "
                    f"minimum ({min_traffic:,})"
                )
            elif prop.traffic_count_vpd >= min_traffic * 0.7:
                score += 15
                reasons.append(
                    f"Traffic ({prop.traffic_count_vpd:,} VPD) is close to "
                    f"minimum ({min_traffic:,})"
                )
            else:
                reasons.append(
                    f"Traffic ({prop.traffic_count_vpd:,} VPD) below "
                    f"minimum ({min_traffic:,})"
                )
        else:
            reasons.append("No traffic count data available")

        # --- Co-tenancy / Void Analysis scoring (up to 35 points) ---
        preferred_cats = requirements.get("preferred_categories", [])

        if void_categories and preferred_cats:
            matching_voids = [
                cat for cat in preferred_cats if cat in void_categories
            ]
            if matching_voids:
                score += 25
                co_tenancy_match = True
                reasons.append(
                    f"Void analysis shows gaps in matching categories: "
                    f"{', '.join(matching_voids)}"
                )
            else:
                reasons.append(
                    "Void analysis categories do not align with tenant type"
                )

            # Bonus for high priority voids
            if void_analysis and void_analysis.high_priority_voids > 0:
                score += 10
                co_tenancy_match = True
                reasons.append(
                    f"{void_analysis.high_priority_voids} high-priority "
                    f"voids identified"
                )
        elif not void_categories:
            reasons.append("No void analysis data available for this property")

        # If we couldn't classify the tenant, give a neutral baseline
        if category is None:
            reasons.insert(0, f"Could not auto-classify tenant '{tenant_name}'")
            # Give partial credit based on raw property metrics
            if prop.traffic_count_vpd and prop.traffic_count_vpd >= 15000:
                score = max(score, 30)
                traffic_match = True
            if prop.population_3mi and prop.population_3mi >= 25000:
                score = max(score, 25)
                demographics_match = True

        # Clamp score to 0-100
        final_score = max(0, min(100, score))

        results.append(
            TenantFitResult(
                tenant_name=tenant_name,
                fit_score=final_score,
                reasons=reasons,
                demographics_match=demographics_match,
                traffic_match=traffic_match,
                co_tenancy_match=co_tenancy_match,
            )
        )

    # Sort by fit_score descending
    results.sort(key=lambda r: r.fit_score, reverse=True)

    logger.info(
        "[tenant_targeting] Scored %d tenants for property %s",
        len(results),
        property_id,
    )

    return results
