"""
Places API — address autocomplete for address-ish inputs.

A thin authenticated proxy over Google Places Autocomplete. The frontend
must never call Google directly: the legacy JSON endpoint has no CORS
headers (browser fetch fails outright), and doing so would require
shipping the API key in the client bundle. The key already lives
server-side as ``settings.google_places_api_key``.

When the key isn't configured (local dev), the endpoint reports
``enabled: false`` so the UI can quietly behave as a plain text input.
"""

import logging

import httpx
from fastapi import APIRouter, Query
from pydantic import BaseModel

from app.api.deps import CurrentUser
from app.core.config import settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/places", tags=["places"])

AUTOCOMPLETE_URL = "https://maps.googleapis.com/maps/api/place/autocomplete/json"
MAX_SUGGESTIONS = 6


class AddressSuggestion(BaseModel):
    description: str
    place_id: str
    main_text: str
    secondary_text: str


class AutocompleteResponse(BaseModel):
    enabled: bool
    suggestions: list[AddressSuggestion]


@router.get("/autocomplete", response_model=AutocompleteResponse)
async def autocomplete_address(
    current_user: CurrentUser,
    q: str = Query(min_length=3, max_length=120),
) -> AutocompleteResponse:
    """Suggest US addresses for a partial query.

    Degrades gracefully: missing key -> ``enabled=false``; upstream errors
    or non-OK statuses -> empty suggestions (the input is an assist, never
    a blocker).
    """
    if not settings.google_places_api_key:
        return AutocompleteResponse(enabled=False, suggestions=[])

    params = {
        "input": q,
        "types": "address",
        "components": "country:us",
        "key": settings.google_places_api_key,
    }
    try:
        async with httpx.AsyncClient(timeout=6.0) as client:
            resp = await client.get(AUTOCOMPLETE_URL, params=params)
            resp.raise_for_status()
            data = resp.json()
    except Exception:
        logger.exception("places autocomplete upstream error")
        return AutocompleteResponse(enabled=True, suggestions=[])

    status = data.get("status")
    if status not in ("OK", "ZERO_RESULTS"):
        logger.warning("places autocomplete status=%s", status)
        return AutocompleteResponse(enabled=True, suggestions=[])

    suggestions: list[AddressSuggestion] = []
    for p in data.get("predictions", [])[:MAX_SUGGESTIONS]:
        description = p.get("description") or ""
        if not description:
            continue
        fmt = p.get("structured_formatting") or {}
        suggestions.append(
            AddressSuggestion(
                description=description,
                place_id=p.get("place_id") or "",
                main_text=fmt.get("main_text") or description,
                secondary_text=fmt.get("secondary_text") or "",
            )
        )
    return AutocompleteResponse(enabled=True, suggestions=suggestions)
