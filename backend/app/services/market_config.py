"""Market configuration service for target market filtering and property classification."""
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.models.deal import Property


@dataclass
class MarketConfig:
    """User's target market configuration."""
    target_states: list[str] = field(default_factory=lambda: ["AZ", "CA", "NV"])
    target_metros: list[str] = field(default_factory=lambda: [
        "Phoenix", "Tucson", "Inland Empire", "Las Vegas"
    ])
    target_product_types: list[str] = field(default_factory=lambda: [
        "retail", "single_tenant", "multi_tenant"
    ])

    def to_dict(self) -> dict[str, Any]:
        return {
            "target_states": self.target_states,
            "target_metros": self.target_metros,
            "target_product_types": self.target_product_types,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "MarketConfig":
        if not data:
            return cls()
        defaults = cls()
        return cls(
            target_states=data.get("target_states", defaults.target_states),
            target_metros=data.get("target_metros", defaults.target_metros),
            target_product_types=data.get("target_product_types", defaults.target_product_types),
        )


@dataclass
class MarketFitResult:
    """Result of checking whether a property fits the user's target market."""
    in_market: bool
    reason: str


def check_market_fit(property: Property, config: MarketConfig) -> MarketFitResult:
    """Check if a property fits the user's target market configuration."""
    # Check state
    if config.target_states and property.state:
        state_upper = property.state.upper().strip()
        # Support both abbreviations and full names
        if state_upper not in [s.upper() for s in config.target_states]:
            return MarketFitResult(
                in_market=False,
                reason=f"State '{property.state}' not in target markets: {', '.join(config.target_states)}"
            )

    # Check metro area
    if config.target_metros and property.metro_area:
        metro_lower = property.metro_area.lower().strip()
        target_metros_lower = [m.lower() for m in config.target_metros]
        if metro_lower not in target_metros_lower:
            return MarketFitResult(
                in_market=False,
                reason=f"Metro '{property.metro_area}' not in target metros: {', '.join(config.target_metros)}"
            )

    # Check product type
    if config.target_product_types and property.product_type:
        pt_lower = property.product_type.lower().strip()
        target_pt_lower = [p.lower() for p in config.target_product_types]
        if pt_lower not in target_pt_lower:
            return MarketFitResult(
                in_market=False,
                reason=f"Product type '{property.product_type}' not in target types: {', '.join(config.target_product_types)}"
            )

    return MarketFitResult(in_market=True, reason="Property matches target market criteria")


# Metro area classification based on city/state
METRO_CLASSIFICATION: dict[str, dict[str, str]] = {
    "AZ": {
        "phoenix": "Phoenix", "scottsdale": "Phoenix", "tempe": "Phoenix",
        "mesa": "Phoenix", "chandler": "Phoenix", "gilbert": "Phoenix",
        "glendale": "Phoenix", "peoria": "Phoenix", "surprise": "Phoenix",
        "goodyear": "Phoenix", "buckeye": "Phoenix", "avondale": "Phoenix",
        "tucson": "Tucson", "marana": "Tucson", "oro valley": "Tucson",
        "flagstaff": "Flagstaff", "prescott": "Prescott",
    },
    "CA": {
        "riverside": "Inland Empire", "san bernardino": "Inland Empire",
        "ontario": "Inland Empire", "rancho cucamonga": "Inland Empire",
        "fontana": "Inland Empire", "moreno valley": "Inland Empire",
        "corona": "Inland Empire", "redlands": "Inland Empire",
        "los angeles": "Los Angeles", "long beach": "Los Angeles",
        "pasadena": "Los Angeles", "glendale": "Los Angeles",
        "san diego": "San Diego", "san francisco": "San Francisco",
        "san jose": "San Jose", "sacramento": "Sacramento",
    },
    "NV": {
        "las vegas": "Las Vegas", "henderson": "Las Vegas",
        "north las vegas": "Las Vegas", "summerlin": "Las Vegas",
        "reno": "Reno", "sparks": "Reno",
    },
}


def auto_classify_property(property: Property) -> dict[str, str | None]:
    """Classify a property's market region, metro area, and product type based on existing data."""
    result: dict[str, str | None] = {
        "market_region": None,
        "metro_area": None,
        "product_type": None,
    }

    # Market region = state abbreviation
    if property.state:
        state = property.state.strip().upper()
        if len(state) == 2:
            result["market_region"] = state
        else:
            # Try to find abbreviation from common state names
            state_map = {
                "arizona": "AZ", "california": "CA", "nevada": "NV",
                "texas": "TX", "florida": "FL", "colorado": "CO",
                "new mexico": "NM", "utah": "UT", "oregon": "OR",
            }
            result["market_region"] = state_map.get(state.lower(), state[:2])

    # Metro area from city + state
    if property.city and result["market_region"]:
        city_lower = property.city.lower().strip()
        state_metros = METRO_CLASSIFICATION.get(result["market_region"], {})
        result["metro_area"] = state_metros.get(city_lower)

    # Product type from property_type
    if property.property_type:
        pt = property.property_type.lower().strip()
        type_map = {
            "retail": "retail",
            "single_tenant": "single_tenant",
            "single tenant": "single_tenant",
            "multi_tenant": "multi_tenant",
            "multi tenant": "multi_tenant",
            "nnn": "single_tenant",
            "strip": "multi_tenant",
            "shopping center": "multi_tenant",
            "pad": "single_tenant",
            "office": "other",
            "industrial": "other",
        }
        result["product_type"] = type_map.get(pt, pt)

    return result
