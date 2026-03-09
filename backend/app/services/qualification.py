"""Property qualification scoring service.

Scores properties on a 0-100 scale across multiple dimensions to help
prioritize acquisitions.
"""
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.models.deal import Property
from app.services.market_config import MarketConfig, check_market_fit, auto_classify_property


@dataclass
class QualificationScore:
    """Composite qualification score for a property."""
    total: int = 0  # 0-100
    market_fit: int = 0  # 0-25
    product_fit: int = 0  # 0-15
    intersection: int = 0  # 0-20
    demographics: int = 0  # 0-20
    pricing: int = 0  # 0-20
    recommendation: str = "pass"  # "pursue" | "save_as_comp" | "pass"
    breakdown: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "total": self.total,
            "market_fit": self.market_fit,
            "product_fit": self.product_fit,
            "intersection": self.intersection,
            "demographics": self.demographics,
            "pricing": self.pricing,
            "recommendation": self.recommendation,
            "breakdown": self.breakdown,
        }


def _score_market_fit(property: Property, config: MarketConfig) -> tuple[int, dict]:
    """Score market fit (0-25)."""
    score = 0
    details: dict[str, Any] = {}

    fit_result = check_market_fit(property, config)
    details["in_market"] = fit_result.in_market
    details["reason"] = fit_result.reason

    if fit_result.in_market:
        score = 15  # Base score for being in market

        # Bonus for primary target metros
        if property.metro_area and config.target_metros:
            primary_metros = config.target_metros[:3]  # Top 3 are primary
            if property.metro_area in primary_metros:
                score += 10
                details["primary_metro"] = True
            else:
                score += 5
                details["primary_metro"] = False

    return min(score, 25), details


def _score_product_fit(property: Property, config: MarketConfig) -> tuple[int, dict]:
    """Score product type fit (0-15)."""
    score = 0
    details: dict[str, Any] = {}

    if not property.product_type:
        details["note"] = "No product type set"
        return 0, details

    pt = property.product_type.lower()
    details["product_type"] = property.product_type

    if config.target_product_types:
        target_lower = [t.lower() for t in config.target_product_types]
        if pt in target_lower:
            score = 15
            details["match"] = True
        else:
            details["match"] = False
    else:
        # No preference set, give partial credit
        score = 8

    return score, details


def _score_intersection(property: Property) -> tuple[int, dict]:
    """Score intersection quality (0-20)."""
    score = 0
    details: dict[str, Any] = {}

    # Intersection quality
    if property.intersection_quality:
        quality = property.intersection_quality.lower()
        details["quality"] = property.intersection_quality
        quality_scores = {
            "signalized": 10,
            "hard_corner": 8,
            "hard corner": 8,
            "corner": 6,
            "mid_block": 3,
            "mid block": 3,
        }
        score += quality_scores.get(quality, 4)

    # Traffic count bonus
    if property.traffic_count_vpd:
        details["vpd"] = property.traffic_count_vpd
        if property.traffic_count_vpd >= 40000:
            score += 10
        elif property.traffic_count_vpd >= 25000:
            score += 7
        elif property.traffic_count_vpd >= 15000:
            score += 5
        elif property.traffic_count_vpd >= 8000:
            score += 3

    return min(score, 20), details


def _score_demographics(property: Property) -> tuple[int, dict]:
    """Score demographics (0-20)."""
    score = 0
    details: dict[str, Any] = {}

    # Population density (3-mile ring)
    if property.population_3mi:
        details["pop_3mi"] = property.population_3mi
        if property.population_3mi >= 100000:
            score += 8
        elif property.population_3mi >= 50000:
            score += 6
        elif property.population_3mi >= 25000:
            score += 4
        elif property.population_3mi >= 10000:
            score += 2

    # Household income
    if property.median_hhi_3mi:
        details["hhi_3mi"] = property.median_hhi_3mi
        if property.median_hhi_3mi >= 100000:
            score += 7
        elif property.median_hhi_3mi >= 75000:
            score += 5
        elif property.median_hhi_3mi >= 50000:
            score += 3
        elif property.median_hhi_3mi >= 35000:
            score += 1

    # 1-mile population (walkability/density indicator)
    if property.population_1mi:
        details["pop_1mi"] = property.population_1mi
        if property.population_1mi >= 20000:
            score += 5
        elif property.population_1mi >= 10000:
            score += 3
        elif property.population_1mi >= 5000:
            score += 1

    return min(score, 20), details


def _score_pricing(property: Property) -> tuple[int, dict]:
    """Score pricing attractiveness (0-20)."""
    score = 0
    details: dict[str, Any] = {}

    # Cap rate (higher = more attractive for acquisitions)
    if property.cap_rate:
        details["cap_rate"] = property.cap_rate
        if property.cap_rate >= 8.0:
            score += 8
        elif property.cap_rate >= 7.0:
            score += 6
        elif property.cap_rate >= 6.0:
            score += 4
        elif property.cap_rate >= 5.0:
            score += 2

    # Price PSF (relative value — lower is generally better)
    if property.price_psf:
        details["price_psf"] = property.price_psf
        if property.price_psf <= 150:
            score += 6
        elif property.price_psf <= 250:
            score += 4
        elif property.price_psf <= 400:
            score += 2

    # NOI presence is a good sign (means income-producing)
    if property.noi:
        details["noi"] = property.noi
        score += 4
        if property.noi >= 200000:
            score += 2

    return min(score, 20), details


async def score_property(
    property_id: str,
    db: AsyncSession,
    market_config: MarketConfig | None = None,
) -> QualificationScore:
    """Score a property across all qualification dimensions.

    Args:
        property_id: The property to score
        db: Database session
        market_config: User's market configuration (uses defaults if None)
    """
    result = await db.execute(
        select(Property).where(Property.id == property_id)
    )
    property = result.scalar_one_or_none()
    if not property:
        raise ValueError(f"Property {property_id} not found")

    config = market_config or MarketConfig()

    # Auto-classify if missing
    if not property.market_region or not property.metro_area:
        classification = auto_classify_property(property)
        if not property.market_region and classification["market_region"]:
            property.market_region = classification["market_region"]
        if not property.metro_area and classification["metro_area"]:
            property.metro_area = classification["metro_area"]
        if not property.product_type and classification["product_type"]:
            property.product_type = classification["product_type"]

    # Score each dimension
    market_score, market_details = _score_market_fit(property, config)
    product_score, product_details = _score_product_fit(property, config)
    intersection_score, intersection_details = _score_intersection(property)
    demographics_score, demographics_details = _score_demographics(property)
    pricing_score, pricing_details = _score_pricing(property)

    total = market_score + product_score + intersection_score + demographics_score + pricing_score

    # Determine recommendation
    if total >= 60:
        recommendation = "pursue"
    elif total >= 30:
        recommendation = "save_as_comp"
    else:
        recommendation = "pass"

    # Override: if not in market, recommend as comp
    if not market_details.get("in_market", True) and recommendation == "pursue":
        recommendation = "save_as_comp"

    score = QualificationScore(
        total=total,
        market_fit=market_score,
        product_fit=product_score,
        intersection=intersection_score,
        demographics=demographics_score,
        pricing=pricing_score,
        recommendation=recommendation,
        breakdown={
            "market_fit": market_details,
            "product_fit": product_details,
            "intersection": intersection_details,
            "demographics": demographics_details,
            "pricing": pricing_details,
        },
    )

    # Persist score to property
    property.qualification_score = total
    property.qualification_data = score.to_dict()
    await db.commit()

    return score
