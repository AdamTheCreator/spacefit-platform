"""
Investment Memo Generator

Generates comprehensive investment memos (one-pagers) for commercial properties.
Combines data from multiple sources:
- Property info (from flyer parser)
- Demographics (from Census API)
- Tenant roster (from Places API)
- Void analysis (from void agent)
- User-provided financials
"""

import json
from datetime import datetime
from typing import Optional

from app.core.config import settings
from app.llm import LLMChatMessage, LLMChatRequest, get_llm_client
from app.services.user_llm import ResolvedLLM


async def generate_investment_memo(
    property_info: dict,
    demographics: dict | None = None,
    tenant_roster: list[dict] | None = None,
    void_analysis: dict | None = None,
    financials: dict | None = None,
    additional_notes: str | None = None,
    resolved_llm: ResolvedLLM | None = None,
) -> dict:
    """
    Generate a comprehensive investment memo from multiple data sources.

    Args:
        property_info: Basic property information (name, address, SF, etc.)
        demographics: Trade area demographics data
        tenant_roster: List of existing/committed tenants
        void_analysis: Void analysis results
        financials: Financial metrics (IRR, rent, cap rate, etc.)
        additional_notes: Any additional context or notes

    Returns:
        dict with structured memo content
    """
    # Build comprehensive context
    context_parts = []

    # Property Info
    if property_info:
        prop_section = ["## Property Information"]
        if property_info.get("name"):
            prop_section.append(f"**Name:** {property_info['name']}")
        if property_info.get("address"):
            addr_parts = [property_info["address"]]
            if property_info.get("city"):
                addr_parts.append(property_info["city"])
            if property_info.get("state"):
                addr_parts.append(property_info["state"])
            if property_info.get("zip_code"):
                addr_parts.append(property_info["zip_code"])
            prop_section.append(f"**Address:** {', '.join(addr_parts)}")
        if property_info.get("total_sf") or property_info.get("gla_sf"):
            sf = property_info.get("gla_sf") or property_info.get("total_sf")
            prop_section.append(f"**GLA:** {sf:,} SF")
        if property_info.get("available_sf"):
            prop_section.append(f"**Available:** {property_info['available_sf']:,} SF")
        if property_info.get("land_area_sf"):
            prop_section.append(f"**Land Area:** {property_info['land_area_sf']:,} SF")
        if property_info.get("property_type"):
            prop_section.append(f"**Type:** {property_info['property_type'].title()}")
        if property_info.get("status"):
            prop_section.append(f"**Status:** {property_info['status']}")
        context_parts.append("\n".join(prop_section))

    # Demographics
    if demographics:
        demo_section = ["## Trade Area Demographics"]
        radius = demographics.get("radius_miles", 3)
        demo_section.append(f"*{radius}-Mile Trade Area*")
        if demographics.get("population"):
            demo_section.append(f"- Population: {demographics['population']:,}")
        if demographics.get("households"):
            demo_section.append(f"- Households: {demographics['households']:,}")
        if demographics.get("median_hh_income") or demographics.get("median_income"):
            income = demographics.get("median_hh_income") or demographics.get("median_income")
            demo_section.append(f"- Median HH Income: ${income:,}")
        if demographics.get("avg_hh_income"):
            demo_section.append(f"- Average HH Income: ${demographics['avg_hh_income']:,}")
        if demographics.get("daytime_employment"):
            demo_section.append(f"- Daytime Employment: {demographics['daytime_employment']:,}")
        if demographics.get("traffic_count"):
            demo_section.append(f"- Traffic Count: {demographics['traffic_count']:,} VPD")
        context_parts.append("\n".join(demo_section))

    # Tenant Roster
    if tenant_roster:
        tenant_section = ["## Tenant Roster"]
        anchors = [t for t in tenant_roster if t.get("is_anchor")]
        inline = [t for t in tenant_roster if not t.get("is_anchor")]

        if anchors:
            tenant_section.append("**Anchors:**")
            for t in anchors:
                line = f"- {t.get('name', 'Unknown')}"
                if t.get("square_footage"):
                    line += f" ({t['square_footage']:,} SF)"
                if t.get("status"):
                    line += f" - {t['status']}"
                tenant_section.append(line)

        if inline:
            tenant_section.append("**In-Line Tenants:**")
            for t in inline[:15]:  # Limit to 15
                line = f"- {t.get('name', 'Unknown')}"
                if t.get("category"):
                    line += f" ({t['category']})"
                tenant_section.append(line)
            if len(inline) > 15:
                tenant_section.append(f"*... and {len(inline) - 15} more*")

        context_parts.append("\n".join(tenant_section))

    # Financials
    if financials:
        fin_section = ["## Investment Highlights"]
        if financials.get("irr"):
            fin_section.append(f"- **IRR:** {financials['irr']}%")
        if financials.get("rental_yield"):
            fin_section.append(f"- **Rental Yield:** {financials['rental_yield']}%")
        if financials.get("exit_cap_rate"):
            fin_section.append(f"- **Exit Cap Rate:** {financials['exit_cap_rate']}%")
        if financials.get("noi"):
            fin_section.append(f"- **Stabilized NOI:** ${financials['noi']:,}")
        if financials.get("total_investment"):
            fin_section.append(f"- **Total Investment:** ${financials['total_investment']:,}")
        if financials.get("land_price"):
            fin_section.append(f"- **Land Price:** ${financials['land_price']:,}")
        if financials.get("asking_rent_psf"):
            rent_type = financials.get("rent_type", "")
            fin_section.append(f"- **Asking Rent:** ${financials['asking_rent_psf']}/SF {rent_type}")
        context_parts.append("\n".join(fin_section))

    # Void Analysis
    if void_analysis:
        void_section = ["## Market Opportunities"]
        if void_analysis.get("summary", {}).get("high_priority"):
            void_section.append("**High Priority Voids:**")
            for void in void_analysis["summary"]["high_priority"][:5]:
                void_section.append(f"- {void}")
        if void_analysis.get("summary", {}).get("key_recommendation"):
            void_section.append(f"\n*{void_analysis['summary']['key_recommendation']}*")
        context_parts.append("\n".join(void_section))

    # Additional Notes
    if additional_notes:
        context_parts.append(f"## Additional Information\n{additional_notes}")

    context = "\n\n".join(context_parts)

    system_prompt = """You are an expert commercial real estate investment analyst. Generate a professional investment memo (one-pager) based on the provided data.

The memo should include:
1. **Executive Summary** - 2-3 compelling sentences about the opportunity
2. **Location Highlights** - Key location benefits (bullet points)
3. **Investment Highlights** - Key financial/investment metrics
4. **Demographics Summary** - Trade area highlights
5. **Tenant Interest/Roster** - Current or committed tenants
6. **Opportunity Analysis** - Why this is a good investment
7. **Key Risks** (optional) - Only if there are notable concerns

Return a JSON object:
{
    "title": "Investment memo title",
    "executive_summary": "2-3 sentence compelling summary",
    "location_highlights": ["Highlight 1", "Highlight 2", ...],
    "investment_highlights": {
        "metrics": [{"label": "IRR", "value": "15%"}, ...],
        "narrative": "Brief investment narrative"
    },
    "demographics_summary": {
        "radius_miles": 3,
        "key_stats": [{"label": "Population", "value": "150,000"}, ...],
        "narrative": "Brief demographics narrative"
    },
    "tenant_summary": {
        "anchors": ["Anchor 1", "Anchor 2"],
        "inline_tenants": ["Tenant 1", "Tenant 2"],
        "occupancy_narrative": "Current occupancy status"
    },
    "opportunity_analysis": "Why this is a compelling opportunity",
    "risks": ["Risk 1"] or null if none significant,
    "recommendation": "Clear investment recommendation"
}

Write in a professional but engaging tone. Highlight the positives while being honest about the opportunity. Return valid JSON only."""

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
                    content=f"Generate an investment memo for this property:\n\n{context}\n\nReturn JSON only.",
                )
            ],
        )
    )

    response_text = response.content.strip()

    # Parse JSON
    try:
        if "```json" in response_text:
            response_text = response_text.split("```json")[1].split("```")[0]
        elif "```" in response_text:
            response_text = response_text.split("```")[1].split("```")[0]

        memo_content = json.loads(response_text)
    except json.JSONDecodeError:
        memo_content = {
            "title": property_info.get("name", "Investment Opportunity"),
            "executive_summary": "Unable to generate summary from provided data.",
            "error": "Failed to parse AI response",
            "raw_data": {
                "property_info": property_info,
                "has_demographics": bool(demographics),
                "has_tenants": bool(tenant_roster),
                "has_financials": bool(financials),
            },
        }

    # Add metadata
    memo_content["generated_at"] = datetime.utcnow().isoformat()
    memo_content["property_address"] = property_info.get("address", "Unknown")

    return memo_content


async def generate_memo_text(
    property_info: dict,
    demographics: dict | None = None,
    tenant_roster: list[dict] | None = None,
    void_analysis: dict | None = None,
    financials: dict | None = None,
    additional_notes: str | None = None,
) -> str:
    """
    Generate a text-formatted investment memo.

    Returns a formatted markdown string.
    """
    memo = await generate_investment_memo(
        property_info=property_info,
        demographics=demographics,
        tenant_roster=tenant_roster,
        void_analysis=void_analysis,
        financials=financials,
        additional_notes=additional_notes,
    )

    lines = []

    # Title
    title = memo.get("title", "Investment Opportunity")
    lines.append(f"# {title}")
    lines.append("")

    # Property address
    if memo.get("property_address"):
        lines.append(f"*{memo['property_address']}*")
        lines.append("")

    # Executive Summary
    if memo.get("executive_summary"):
        lines.append("## Executive Summary")
        lines.append(memo["executive_summary"])
        lines.append("")

    # Location Highlights
    if memo.get("location_highlights"):
        lines.append("## Location Highlights")
        for highlight in memo["location_highlights"]:
            lines.append(f"- {highlight}")
        lines.append("")

    # Investment Highlights
    inv = memo.get("investment_highlights", {})
    if inv:
        lines.append("## Investment Highlights")
        if inv.get("metrics"):
            for metric in inv["metrics"]:
                lines.append(f"- **{metric['label']}:** {metric['value']}")
        if inv.get("narrative"):
            lines.append("")
            lines.append(inv["narrative"])
        lines.append("")

    # Demographics
    demo = memo.get("demographics_summary", {})
    if demo:
        radius = demo.get("radius_miles", 3)
        lines.append(f"## Trade Area Demographics ({radius}-mile)")
        if demo.get("key_stats"):
            for stat in demo["key_stats"]:
                lines.append(f"- **{stat['label']}:** {stat['value']}")
        if demo.get("narrative"):
            lines.append("")
            lines.append(demo["narrative"])
        lines.append("")

    # Tenant Summary
    tenant = memo.get("tenant_summary", {})
    if tenant:
        lines.append("## Tenant Summary")
        if tenant.get("anchors"):
            lines.append(f"**Anchors:** {', '.join(tenant['anchors'])}")
        if tenant.get("inline_tenants"):
            lines.append(f"**In-Line:** {', '.join(tenant['inline_tenants'][:10])}")
        if tenant.get("occupancy_narrative"):
            lines.append("")
            lines.append(tenant["occupancy_narrative"])
        lines.append("")

    # Opportunity Analysis
    if memo.get("opportunity_analysis"):
        lines.append("## Opportunity Analysis")
        lines.append(memo["opportunity_analysis"])
        lines.append("")

    # Risks (if any)
    if memo.get("risks"):
        lines.append("## Key Considerations")
        for risk in memo["risks"]:
            lines.append(f"- {risk}")
        lines.append("")

    # Recommendation
    if memo.get("recommendation"):
        lines.append("## Recommendation")
        lines.append(memo["recommendation"])
        lines.append("")

    # Footer
    lines.append("---")
    lines.append(f"*Generated by SpaceFit AI on {datetime.utcnow().strftime('%B %d, %Y')}*")

    return "\n".join(lines)


async def generate_memo_from_property_id(
    property_id: str,
    db_session,
    include_demographics: bool = True,
    include_tenants: bool = True,
    include_voids: bool = True,
) -> dict:
    """
    Generate an investment memo for a property in the database.

    Pulls property info, documents, and runs agents as needed.
    """
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload

    from app.db.models.deal import Property
    from app.db.models.document import ParsedDocument
    from app.services.census import analyze_demographics
    from app.services.places import analyze_tenant_roster
    from app.agents.void_analysis import analyze_voids_for_property

    # Get property
    result = await db_session.execute(
        select(Property).where(Property.id == property_id)
    )
    property_obj = result.scalar_one_or_none()

    if not property_obj:
        return {"error": "Property not found"}

    # Build property info
    property_info = {
        "name": property_obj.name,
        "address": property_obj.address,
        "city": property_obj.city,
        "state": property_obj.state,
        "zip_code": property_obj.zip_code,
        "total_sf": property_obj.total_sf,
        "available_sf": property_obj.available_sf,
        "property_type": property_obj.property_type,
    }

    full_address = f"{property_obj.address}, {property_obj.city}, {property_obj.state}"

    # Get demographics
    demographics = None
    if include_demographics:
        try:
            demo_text = await analyze_demographics(full_address)
            # Parse the text response into structured data (simplified)
            demographics = {
                "radius_miles": 3,
                "raw_data": demo_text,
            }
        except Exception:
            pass

    # Get tenant roster
    tenant_roster = None
    if include_tenants:
        try:
            # Check for parsed documents with tenant data
            doc_result = await db_session.execute(
                select(ParsedDocument)
                .options(selectinload(ParsedDocument.existing_tenants))
                .where(
                    ParsedDocument.property_id == property_id,
                    ParsedDocument.document_type == "leasing_flyer",
                )
                .order_by(ParsedDocument.created_at.desc())
                .limit(1)
            )
            doc = doc_result.scalar_one_or_none()

            if doc and doc.existing_tenants:
                tenant_roster = [
                    {
                        "name": t.name,
                        "category": t.category,
                        "square_footage": t.square_footage,
                        "is_anchor": t.is_anchor,
                        "is_national": t.is_national,
                    }
                    for t in doc.existing_tenants
                ]
        except Exception:
            pass

    # Get void analysis
    void_analysis = None
    if include_voids:
        try:
            void_analysis = await analyze_voids_for_property(
                address=full_address,
                existing_tenants=tenant_roster,
                demographics=demographics,
            )
        except Exception:
            pass

    # Generate memo
    return await generate_investment_memo(
        property_info=property_info,
        demographics=demographics,
        tenant_roster=tenant_roster,
        void_analysis=void_analysis,
    )
