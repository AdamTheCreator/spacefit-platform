"""Perigee MCP Server -- FastMCP-based.

Registers every tool as an @mcp.tool() with gateway middleware applied.
Mounted at /mcp in the FastAPI app (see backend/app/main.py).

Tools are organized by category:
  - Free/public data: business_search, demographics_analysis, tenant_roster
  - LLM synthesis:    void_analysis
  - User imports:     costar_import, placer_import, siteusa_import
  - Actions:          draft_outreach

To add a new tool: write the async function, decorate with @mcp.tool()
and @audit_and_limit("tool_name"). That's it.

User attribution is passed via contextvars (see mcp.context), not
function parameters -- the MCP SDK rejects parameter names starting
with '_'.
"""

from __future__ import annotations

import logging
from typing import Any

from mcp.server.fastmcp import FastMCP

from app.mcp.gateway import audit_and_limit

logger = logging.getLogger(__name__)

mcp = FastMCP("perigee")


# ---------------------------------------------------------------------------
# Free / public data tools
# ---------------------------------------------------------------------------


@mcp.tool(
    description="Search for businesses by type and location using real-time Google Places data. "
    "Use when the user asks about businesses in a specific location, nearby competitors, "
    "restaurants, stores, or any commercial establishments. `location` must be a concrete "
    "address/city/neighborhood — if the session is scoped to a project, default it to the "
    "project's property address unless the user names another place; never pass vague "
    "placeholders like 'the location' or 'this property'."
)
@audit_and_limit("business_search")
async def business_search(
    location: str,
    query: str = "",
    business_type: str = "",
    radius_miles: float = 2.0,
) -> str:
    from app.services.business_search import search_businesses

    result = await search_businesses(
        query=query or None,
        business_type=business_type or None,
        location=location,
        radius_miles=max(0.25, min(25.0, radius_miles)),
    )
    return result.to_formatted_report()


@mcp.tool(
    description="Analyze trade area demographics using Census ACS data. "
    "Use for population, income, age distribution, household size in a geographic area. "
    "Default radius is 3 miles. Supported: 1, 3, 5, 10. `address` must be a concrete "
    "street address — default to the project's property address when the session is "
    "scoped to a project, and never pass vague placeholders."
)
@audit_and_limit("demographics_analysis")
async def demographics_analysis(
    address: str,
    radius_miles: float = 3.0,
) -> str:
    from app.services.census import analyze_demographics

    return await analyze_demographics(
        address, radius_miles=max(0.5, min(25.0, radius_miles))
    )


@mcp.tool(
    description="Get the current tenant roster for a shopping center or commercial property "
    "from Google Places. For deeper lease details, use costar_import instead. `address` must "
    "be a concrete street address — default to the project's property address when the "
    "session is scoped to a project, and never pass vague placeholders."
)
@audit_and_limit("tenant_roster")
async def tenant_roster(
    address: str,
    radius_miles: float = 1.0,
) -> str:
    from app.services.places import analyze_tenant_roster

    return await analyze_tenant_roster(
        address, radius_miles=max(0.5, min(25.0, radius_miles))
    )


# ---------------------------------------------------------------------------
# LLM synthesis tools
# ---------------------------------------------------------------------------


@mcp.tool(
    description="Identify missing tenant categories and opportunities for a property. "
    "Best after demographics and tenant roster have been gathered. `address` must be a "
    "concrete street address — default to the project's property address when the "
    "session is scoped to a project, and never pass vague placeholders."
)
@audit_and_limit("void_analysis")
async def void_analysis(
    address: str,
    radius_miles: float = 3.0,
) -> str:
    from app.services.census import get_demographics_structured
    from app.services.places import get_tenants_structured
    from app.services.void_analysis import generate_void_report

    radius = max(0.5, min(25.0, radius_miles))
    demographics_data = await get_demographics_structured(address)
    tenants_data = await get_tenants_structured(address, radius_miles=radius)
    return await generate_void_report(
        property_address=address,
        existing_tenants=tenants_data,
        demographics=demographics_data,
        radius_miles=radius,
    )


# ---------------------------------------------------------------------------
# User-imported data tools
# ---------------------------------------------------------------------------


@mcp.tool(
    description="Read a user-uploaded CoStar CSV export and return normalized property + tenant data. "
    "Use when the user's context mentions they've uploaded CoStar data."
)
@audit_and_limit("costar_import")
async def costar_import(
    import_job_id: str,
) -> str:
    from sqlalchemy import select

    from app.core.database import async_session_factory
    from app.db.models.import_job import ImportJob

    async with async_session_factory() as db:
        result = await db.execute(
            select(ImportJob).where(
                ImportJob.id == import_job_id,
                ImportJob.source == "costar",
            )
        )
        job = result.scalar_one_or_none()

    if not job:
        return f"CoStar import job {import_job_id} not found."
    if job.status != "ready":
        return f"CoStar import job {import_job_id} is still {job.status}."
    if not job.parsed_payload_json:
        return "CoStar import has no parsed data."

    return f"CoStar Import Data ({job.original_filename}):\n{job.parsed_payload_json}"


@mcp.tool(
    description="Read a user-uploaded Placer.ai property report PDF and return trade area metrics "
    "(visits, dwell time, home ZIPs, visitor demographics)."
)
@audit_and_limit("placer_import")
async def placer_import(
    import_job_id: str,
) -> str:
    from sqlalchemy import select

    from app.core.database import async_session_factory
    from app.db.models.import_job import ImportJob

    async with async_session_factory() as db:
        result = await db.execute(
            select(ImportJob).where(
                ImportJob.id == import_job_id,
                ImportJob.source == "placer",
            )
        )
        job = result.scalar_one_or_none()

    if not job:
        return f"Placer import job {import_job_id} not found."
    if job.status != "ready":
        return f"Placer import job {import_job_id} is still {job.status}."
    if not job.parsed_payload_json:
        return "Placer import has no parsed data."

    return f"Placer Trade Area Data ({job.original_filename}):\n{job.parsed_payload_json}"


@mcp.tool(
    description="Read a user-uploaded SiteUSA CSV export and return vehicle traffic + demographics data."
)
@audit_and_limit("siteusa_import")
async def siteusa_import(
    import_job_id: str,
) -> str:
    from sqlalchemy import select

    from app.core.database import async_session_factory
    from app.db.models.import_job import ImportJob

    async with async_session_factory() as db:
        result = await db.execute(
            select(ImportJob).where(
                ImportJob.id == import_job_id,
                ImportJob.source == "siteusa",
            )
        )
        job = result.scalar_one_or_none()

    if not job:
        return f"SiteUSA import job {import_job_id} not found."
    if job.status != "ready":
        return f"SiteUSA import job {import_job_id} is still {job.status}."
    if not job.parsed_payload_json:
        return "SiteUSA import has no parsed data."

    return f"SiteUSA Traffic Data ({job.original_filename}):\n{job.parsed_payload_json}"


# ---------------------------------------------------------------------------
# Action tools
# ---------------------------------------------------------------------------


@mcp.tool(
    description="Draft personalized outreach emails to a list of target tenants for a property "
    "vacancy. Returns drafts for user review. Does NOT send."
)
@audit_and_limit("draft_outreach")
async def draft_outreach(
    property_address: str,
    vacancy_description: str = "Available space",
    target_tenants: list[dict[str, Any]] | None = None,
) -> str:
    from app.services.outreach_drafts import draft_outreach_emails

    if not target_tenants:
        return "draft_outreach requires at least one target tenant."

    drafts = await draft_outreach_emails(
        property_address=property_address,
        vacancy_description=vacancy_description,
        target_tenants=target_tenants,
    )

    lines = [f"## {len(drafts)} Outreach Drafts Generated\n"]
    for i, d in enumerate(drafts, 1):
        lines.append(f"### Draft {i}: {d.tenant_name}")
        lines.append(f"**To:** {d.recipient_email or '(no email provided)'}")
        lines.append(f"**Subject:** {d.subject}")
        if d.rationale:
            lines.append(f"**Rationale:** {d.rationale}")
        lines.append(f"\n{d.body[:500]}{'...' if len(d.body) > 500 else ''}\n")

    return "\n".join(lines)
