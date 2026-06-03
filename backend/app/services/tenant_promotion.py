"""Promote void-analysis tenant suggestions into the Contacts directory.

This is the "void → Contacts" leg of the spine: a void/tenant-gap analysis
surfaces recruitable tenant brands (``categories[].suggested_tenants`` in the
``void_analysis`` JSON), and this module turns the ones the user picks into
``Company`` rows in the contacts directory — so they can then flow into an
outreach campaign (void → contacts → campaign).

Three pieces:

* ``extract_promotable_tenants`` — pure. Flattens a void-analysis result dict
  into a deduped, ranked list of promotable tenant entries.
* A per-turn capture sink (``begin_tenant_capture`` / ``record_promotable_tenants``)
  — lets the chat WS layer surface the *exact* tenants a void run produced via a
  ``tenant_candidates`` event, with no second LLM call and no markdown scraping.
  Gated on a ``ContextVar`` so non-chat callers (reports, tests) are unaffected.
* ``promote_tenants_to_contacts`` — writes ``Company`` rows, de-duplicated by
  name within the user (mirrors the CSV importer), recording provenance in the
  ``criteria`` buy-box JSON.
"""

from __future__ import annotations

import contextvars
import logging

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.contact import Company

logger = logging.getLogger(__name__)

# Defensive caps so a runaway analysis can't flood the directory.
MAX_PROMOTABLE_TENANTS = 50


# --------------------------------------------------------------------------- #
# Pure extraction
# --------------------------------------------------------------------------- #
def extract_promotable_tenants(
    analysis: dict | None, source_address: str = ""
) -> list[dict]:
    """Flatten a ``void_analysis`` result dict into promotable tenant entries.

    Walks the ``categories`` that are flagged ``is_void`` (highest match score
    first), emitting one entry per ``suggested_tenants`` brand. A void category
    with no named brands still yields a single category-level target so the user
    gets something to save. Entries are de-duplicated by name (case-insensitive,
    first occurrence wins) and capped at ``MAX_PROMOTABLE_TENANTS``.

    Pure + deterministic — no I/O — so it's unit-testable without an LLM.
    """
    if not isinstance(analysis, dict):
        return []

    categories = analysis.get("categories")
    if not isinstance(categories, list):
        return []

    # Rank by match score so the strongest opportunities lead (mirrors the
    # report ordering); missing scores sort last.
    def _score(cat: object) -> int:
        if isinstance(cat, dict):
            try:
                return int(cat.get("match_score") or 0)
            except (TypeError, ValueError):
                return 0
        return 0

    ordered = sorted(
        (c for c in categories if isinstance(c, dict) and c.get("is_void")),
        key=_score,
        reverse=True,
    )

    out: list[dict] = []
    seen: set[str] = set()
    for cat in ordered:
        sector_raw = cat.get("parent_category") or cat.get("category_name") or ""
        sector = sector_raw.strip() or None
        category = (cat.get("category_name") or "").strip() or None
        sf = cat.get("estimated_sf_need")
        try:
            estimated_sf = int(sf) if sf else None
        except (TypeError, ValueError):
            estimated_sf = None
        priority = (cat.get("priority") or "").strip().lower() or None
        rationale = (cat.get("rationale") or "").strip() or None
        score = _score(cat) or None

        brands = cat.get("suggested_tenants")
        names = (
            [str(b).strip() for b in brands if str(b).strip()]
            if isinstance(brands, list)
            else []
        )
        # No named brands? fall back to the category itself as a type-level target.
        if not names and category:
            names = [category]

        for name in names:
            key = name.lower()
            if not key or key in seen:
                continue
            seen.add(key)
            out.append(
                {
                    "name": name,
                    "sector": sector,
                    "category": category,
                    "estimated_sf": estimated_sf,
                    "priority": priority,
                    "match_score": score,
                    "rationale": rationale,
                    "source_address": source_address or None,
                }
            )
            if len(out) >= MAX_PROMOTABLE_TENANTS:
                return out

    return out


# --------------------------------------------------------------------------- #
# Per-turn capture sink (so the chat layer can surface the exact tenants)
# --------------------------------------------------------------------------- #
# Holds the active turn's sink list, or ``None`` when capture is off. Set by the
# chat WS handler at the start of a turn; read by ``analyze_voids_for_property``
# deep inside tool execution. ContextVars propagate into the tasks that
# ``asyncio.create_task`` / ``asyncio.gather`` spawn, so the value set on the
# turn is visible to the void tool even though it runs several awaits down.
_tenant_capture_sink: contextvars.ContextVar[list | None] = contextvars.ContextVar(
    "tenant_capture_sink", default=None
)


def begin_tenant_capture() -> list:
    """Start capturing promotable tenants for the current turn.

    Returns the sink list (the caller drains it after the turn). Overwrites any
    previous turn's sink so candidates never leak across turns.
    """
    sink: list = []
    _tenant_capture_sink.set(sink)
    return sink


def record_promotable_tenants(tenants: list[dict]) -> None:
    """Append into the active turn's sink, if capture is on (else a no-op).

    Best-effort and never raises — surfacing tenant candidates must never break
    a void analysis.
    """
    if not tenants:
        return
    sink = _tenant_capture_sink.get()
    if sink is not None:
        sink.extend(tenants)


# --------------------------------------------------------------------------- #
# Persistence
# --------------------------------------------------------------------------- #
async def promote_tenants_to_contacts(
    db: AsyncSession,
    user_id: str,
    tenants: list[dict],
    source: dict | None = None,
) -> dict:
    """Create ``Company`` rows from promotable tenant entries, de-duped by name.

    De-duplication mirrors the CSV importer: a tenant whose name already matches
    one of the user's companies (case-insensitive) is skipped, not duplicated.
    Provenance (the source property + void category + score) is stored in the
    company's ``criteria`` buy-box JSON so the row is traceable and the future
    client-fit Search has something to score against.

    Returns ``{created, skipped, companies: [{id, name, sector}]}``.
    """
    source = source or {}
    source_address = source.get("address") or ""

    # Preload existing company names for this user so the promote de-dupes.
    existing_rows = (
        await db.execute(
            select(func.lower(Company.name)).where(Company.user_id == user_id)
        )
    ).scalars().all()
    seen: set[str] = {n for n in existing_rows if n}

    created: list[Company] = []
    skipped = 0
    for tenant in tenants:
        name = str(tenant.get("name", "")).strip()
        key = name.lower()
        if not name or key in seen:
            skipped += 1
            continue
        seen.add(key)

        estimated_sf = tenant.get("estimated_sf")
        try:
            estimated_sf = int(estimated_sf) if estimated_sf else None
        except (TypeError, ValueError):
            estimated_sf = None

        rationale = (tenant.get("rationale") or "").strip() or None
        criteria = {
            "source": "void_analysis",
            "source_property": tenant.get("source_address") or source_address or None,
            "void_category": tenant.get("category") or None,
            "match_score": tenant.get("match_score"),
            "priority": tenant.get("priority") or None,
        }
        if rationale:
            criteria["free_form"] = rationale

        company = Company(
            user_id=user_id,
            name=name,
            sector=(tenant.get("sector") or None),
            sf_min=estimated_sf,
            sf_max=estimated_sf,
            is_expanding=True,
            criteria=criteria,
            notes=rationale,
        )
        db.add(company)
        created.append(company)

    if created:
        # flush so the DB-side id defaults populate before we read them back
        await db.flush()
    await db.commit()

    return {
        "created": len(created),
        "skipped": skipped,
        "companies": [
            {"id": c.id, "name": c.name, "sector": c.sector} for c in created
        ],
    }
