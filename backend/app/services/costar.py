"""
CoStar Service Layer

Typed dataclasses and high-level entry points for CoStar data.
Browser automation details live in agents/costar.py and scrapers/costar.py;
this module provides a clean interface for the rest of the application and
a future API-mode path.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class TenantLease:
    """A single tenant row from a CoStar tenant roster."""
    name: str
    suite: str = ""
    sqft: int | None = None
    lease_type: str = ""          # NNN, Gross, Modified Gross, etc.
    rent_psf: float | None = None
    expiration: str = ""          # date string as returned by CoStar
    category: str = ""            # F&B, Apparel, Services, etc.


@dataclass
class PropertyInfo:
    """CoStar property-level detail."""
    name: str
    address: str
    property_type: str = ""
    year_built: str = ""
    sqft: int | None = None
    floors: int | None = None
    parking: str = ""
    owner: str = ""
    sale_history: list[dict] = field(default_factory=list)
    occupancy: str = ""


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

def format_property_info(data: dict, address: str) -> str:
    """Format raw CoStar property data dict into a Markdown report.

    Extracted from the inline formatting in CoStarPropertyAgent.execute()
    so it can be reused elsewhere (e.g. service-layer callers, tests).
    """
    lines = [
        f"**Property Details for {data.get('name', address)}**\n",
        f"*{address}*\n",
    ]

    if data.get("property_type"):
        lines.append(f"**Property Type:** {data['property_type']}")
    if data.get("year_built"):
        lines.append(f"**Year Built:** {data['year_built']}")
    if data.get("total_sqft"):
        lines.append(f"**Total SF:** {data['total_sqft']}")
    if data.get("floors"):
        lines.append(f"**Floors:** {data['floors']}")
    if data.get("parking_spaces"):
        lines.append(f"**Parking:** {data['parking_spaces']} spaces")
    if data.get("lot_size"):
        lines.append(f"**Lot Size:** {data['lot_size']}")

    if data.get("owner"):
        lines.append(f"\n**Owner:** {data['owner']}")

    if data.get("last_sale_date") or data.get("last_sale_price"):
        lines.append("\n**Sale History:**")
        if data.get("last_sale_date"):
            lines.append(f"- Last Sale Date: {data['last_sale_date']}")
        if data.get("last_sale_price"):
            lines.append(f"- Last Sale Price: {data['last_sale_price']}")

    if data.get("occupancy"):
        lines.append(f"\n**Occupancy:** {data['occupancy']}")

    lines.append("\n> **Source:** CoStar Group")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# High-level async entry points (thin wrappers for future API mode)
# ---------------------------------------------------------------------------

async def get_tenant_roster(address: str, *, user_id: str | None = None, credential=None) -> str:
    """Retrieve a CoStar tenant roster for *address*.

    Previously delegated to browser-based CoStarTenantAgent (now removed).
    """
    # TODO: Re-implement in Phase 2 (CoStar agents were removed)
    raise NotImplementedError("CoStar tenant roster agent is not available — pending re-implementation.")


async def get_property_info(address: str, *, user_id: str | None = None, credential=None) -> str:
    """Retrieve CoStar property info for *address*.

    Previously delegated to browser-based CoStarPropertyAgent (now removed).
    """
    # TODO: Re-implement in Phase 2 (CoStar agents were removed)
    raise NotImplementedError("CoStar property info agent is not available — pending re-implementation.")
