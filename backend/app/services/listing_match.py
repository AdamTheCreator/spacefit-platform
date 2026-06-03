"""Client-fit scoring service.

The inverse of the void/matchmaker flow: given a client ``Company`` (its
acquisition "buy box") and a set of imported ``PropertyListing`` rows, ask the
LLM to score each listing's fit to that client and return a ranked-ish JSON
array. The endpoint joins the scores back to the listing objects and sorts.

The buy-box text builder and the score-array parser are pure functions so they
can be unit-tested without a live DB or LLM. LLM calling style mirrors
``app.services.void_analysis`` (BYOK-aware via ``ResolvedLLM``).
"""

from __future__ import annotations

import json
from typing import Any

from app.core.config import settings
from app.llm import LLMChatMessage, LLMChatRequest, get_llm_client
from app.services.user_llm import ResolvedLLM

# Cap how many listings we feed the model in one shot — keeps the prompt
# bounded and the single call cheap. The endpoint already clamps by `limit`,
# this is the hard backstop.
MAX_LISTINGS = 50


def _fmt_money(value: int | float | None) -> str | None:
    """Render whole-dollar amounts as ``$1,250,000``; ``None`` passes through."""
    if value is None:
        return None
    try:
        return f"${int(value):,}"
    except (TypeError, ValueError):
        return None


def build_buybox_text(company: Any) -> str:
    """Render a compact "buy box" description for the scoring prompt.

    Pulls from the flexible ``criteria`` JSON (asset_types / budget_min /
    budget_max / cap_rate_max / geographies / free_form) plus the structured
    ``Company`` columns (name / sector / subsector / sf_min / sf_max /
    target_markets / is_expanding). Pure + deterministic so it is unit-testable
    without an LLM. Only non-empty fields are emitted.
    """
    criteria = getattr(company, "criteria", None) or {}
    lines: list[str] = []

    name = getattr(company, "name", None)
    if name:
        lines.append(f"Client: {name}")

    sector = getattr(company, "sector", None)
    subsector = getattr(company, "subsector", None)
    if sector or subsector:
        sect = " / ".join(p for p in (sector, subsector) if p)
        lines.append(f"Sector: {sect}")

    asset_types = criteria.get("asset_types")
    if asset_types:
        if isinstance(asset_types, (list, tuple)):
            asset_types = ", ".join(str(a) for a in asset_types)
        lines.append(f"Target asset types: {asset_types}")

    budget_min = _fmt_money(criteria.get("budget_min"))
    budget_max = _fmt_money(criteria.get("budget_max"))
    if budget_min or budget_max:
        lo = budget_min or "n/a"
        hi = budget_max or "n/a"
        lines.append(f"Budget: {lo} to {hi}")

    cap_rate_max = criteria.get("cap_rate_max")
    if cap_rate_max is not None:
        lines.append(f"Max acceptable cap rate: {cap_rate_max}%")

    sf_min = getattr(company, "sf_min", None)
    sf_max = getattr(company, "sf_max", None)
    if sf_min is not None or sf_max is not None:
        lo = f"{sf_min:,}" if isinstance(sf_min, int) else "n/a"
        hi = f"{sf_max:,}" if isinstance(sf_max, int) else "n/a"
        lines.append(f"Size range (SF): {lo} to {hi}")

    geographies = criteria.get("geographies")
    if geographies:
        if isinstance(geographies, (list, tuple)):
            geographies = ", ".join(str(g) for g in geographies)
        lines.append(f"Geographies: {geographies}")

    target_markets = getattr(company, "target_markets", None)
    if target_markets:
        if isinstance(target_markets, (list, tuple)):
            target_markets = ", ".join(str(m) for m in target_markets)
        lines.append(f"Target markets: {target_markets}")

    is_expanding = getattr(company, "is_expanding", None)
    if is_expanding is not None:
        lines.append(
            "Actively expanding: yes" if is_expanding else "Actively expanding: no"
        )

    free_form = criteria.get("free_form")
    if free_form:
        lines.append(f"Notes: {free_form}")

    if not lines:
        return "No explicit buy-box criteria on file for this client."
    return "\n".join(lines)


def format_listings_for_prompt(listings: list[Any]) -> str:
    """Render a compact numbered list of listings (id + key facts).

    Each line leads with the listing id so the model can echo it back in its
    JSON output for an unambiguous join. Pure + deterministic.
    """
    out: list[str] = []
    for listing in listings[:MAX_LISTINGS]:
        facts: list[str] = []
        loc_parts = [
            getattr(listing, "address", None),
            getattr(listing, "city", None),
            getattr(listing, "state", None),
            getattr(listing, "zip_code", None),
        ]
        loc = ", ".join(str(p) for p in loc_parts if p)
        if loc:
            facts.append(loc)
        asset_type = getattr(listing, "asset_type", None)
        if asset_type:
            facts.append(f"type={asset_type}")
        size_sf = getattr(listing, "size_sf", None)
        if size_sf:
            facts.append(f"{size_sf:,} SF")
        units = getattr(listing, "units", None)
        if units:
            facts.append(f"{units} units")
        price = _fmt_money(getattr(listing, "price", None))
        if price:
            facts.append(f"price={price}")
        cap_rate = getattr(listing, "cap_rate", None)
        if cap_rate is not None:
            facts.append(f"cap={cap_rate}%")
        year_built = getattr(listing, "year_built", None)
        if year_built:
            facts.append(f"built {year_built}")
        description = getattr(listing, "description", None)
        if description:
            facts.append(str(description)[:160])
        listing_id = getattr(listing, "id", "")
        out.append(f"[{listing_id}] " + " | ".join(facts))
    return "\n".join(out)


def parse_score_array(response_text: str) -> list[dict]:
    """Parse the model's JSON score array, tolerating fences / prose / garbage.

    Expected payload: ``[{"listing_id", "fit_score", "rationale", "flags"}]``.
    Handles ```json fenced blocks and a bare array embedded in prose. Any
    failure (bad JSON, wrong top-level type) degrades to ``[]``. Pure +
    deterministic so it is unit-testable without an LLM.
    """
    text = (response_text or "").strip()
    if not text:
        return []

    if "```json" in text:
        text = text.split("```json", 1)[1].split("```", 1)[0]
    elif "```" in text:
        text = text.split("```", 1)[1].split("```", 1)[0]
    text = text.strip()

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        # Last resort: slice out the outermost array if it's wrapped in prose.
        start = text.find("[")
        end = text.rfind("]")
        if start == -1 or end == -1 or end <= start:
            return []
        try:
            parsed = json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            return []

    if not isinstance(parsed, list):
        return []

    cleaned: list[dict] = []
    for item in parsed:
        if not isinstance(item, dict):
            continue
        listing_id = item.get("listing_id")
        if not listing_id:
            continue
        try:
            fit_score = int(item.get("fit_score", 0))
        except (TypeError, ValueError):
            fit_score = 0
        fit_score = max(0, min(100, fit_score))
        flags = item.get("flags") or []
        if not isinstance(flags, list):
            flags = [str(flags)]
        cleaned.append(
            {
                "listing_id": str(listing_id),
                "fit_score": fit_score,
                "rationale": str(item.get("rationale", "")),
                "flags": [str(f) for f in flags],
            }
        )
    return cleaned


_SYSTEM_PROMPT = (
    "You are a commercial real estate acquisitions analyst. You are given a "
    "single client's acquisition buy-box and a numbered list of for-sale "
    "property listings. Score how well EACH listing fits THIS client's "
    "buy-box, considering asset type, price/budget, cap rate, size, location, "
    "and any stated preferences. A perfect fit is 100; a clear mismatch is 0. "
    "When a listing is missing data needed to judge fit, score conservatively "
    "and note it as a flag. Use `flags` for concise risk/mismatch callouts "
    "(e.g. 'over budget', 'wrong asset type', 'cap rate below target', "
    "'no price'). Keep each rationale to one line.\n\n"
    "Return ONLY a JSON array, no prose, with one object per listing using the "
    'listing id from the brackets:\n'
    '[{"listing_id": "<id>", "fit_score": 0-100, "rationale": "one line", '
    '"flags": ["..."]}]'
)


async def match_listings_for_client(
    company: Any,
    listings: list[Any],
    resolved_llm: ResolvedLLM | None = None,
) -> list[dict]:
    """Score each listing's fit to the client's buy-box in one LLM call.

    Returns the parsed score list (``[{listing_id, fit_score, rationale,
    flags}]``); the caller joins these back to the listing objects and sorts by
    ``fit_score``. BYOK-aware: routes through ``resolved_llm.client`` /
    ``resolved_llm.model`` when provided, else the platform default. With no
    listings, short-circuits to ``[]`` (no LLM call).
    """
    if not listings:
        return []

    buybox = build_buybox_text(company)
    listings_block = format_listings_for_prompt(listings)

    llm = resolved_llm.client if resolved_llm else get_llm_client()
    model = (
        resolved_llm.model
        if resolved_llm
        else (settings.llm_model or settings.anthropic_model)
    )

    user_content = (
        "CLIENT BUY-BOX:\n"
        f"{buybox}\n\n"
        "LISTINGS TO SCORE (each line is `[id] facts`):\n"
        f"{listings_block}\n\n"
        "Score every listing. Return the JSON array only."
    )

    response = await llm.chat(
        LLMChatRequest(
            model=model,
            max_tokens=4096,
            system=_SYSTEM_PROMPT,
            messages=[LLMChatMessage(role="user", content=user_content)],
        )
    )

    return parse_score_array(response.content)
