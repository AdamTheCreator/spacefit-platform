"""Traffic-count lookup — vehicles/day (AADT) near a property, from free public
state-DOT data. Powers the property "Traffic counts" card; the chat agent uses
the ``traffic_counts`` MCP tool for the same data.
"""

from fastapi import APIRouter, Query

from app.api.deps import CurrentUser
from app.services.location_resolver import resolve_location
from app.services.traffic_counts import covered_states, get_traffic_count

router = APIRouter(tags=["traffic"])


@router.get("/traffic/counts")
async def lookup_traffic_count(
    current_user: CurrentUser,
    address: str = Query(..., min_length=3, description="Property address to look up"),
) -> dict:
    """Nearest official daily traffic count (AADT) for an address — or why there's none.

    Always returns 200 with a ``found`` flag so the UI can render a clean empty
    state (uncovered state / no nearby station) instead of treating it as an error.
    """
    covered = covered_states()
    resolved = await resolve_location(address)
    if not resolved.has_coordinates():
        return {"found": False, "reason": "ungeocodable", "covered_states": covered}

    count = await get_traffic_count(
        resolved.latitude, resolved.longitude, resolved.state_abbrev
    )
    if count is None:
        state = (resolved.state_abbrev or "").upper()
        reason = "no_station" if state in covered else "state_uncovered"
        return {
            "found": False,
            "reason": reason,
            "state": state or None,
            "covered_states": covered,
        }
    return {"found": True, "covered_states": covered, **count.to_dict()}
