"""
Project context builder — aggregates all project documents + instructions
into a single context block for injection into the AI system prompt.
"""
import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models.document import DocumentStatus, ParsedDocument
from app.db.models.project import Project

logger = logging.getLogger(__name__)

# Hard cap to avoid system prompt bloat
MAX_PROJECT_CONTEXT_TOKENS = 8000  # rough char estimate (1 token ~ 4 chars)
MAX_CONTEXT_CHARS = MAX_PROJECT_CONTEXT_TOKENS * 4


def summarize_extracted_data(doc: ParsedDocument) -> dict[str, Any]:
    """
    Condense a document's extracted_data to key fields and a compact
    content summary suitable for project-chat context injection.
    """
    data = doc.extracted_data or {}
    summary: dict[str, Any] = {
        "filename": doc.filename,
        "document_type": doc.document_type,
        "confidence_score": doc.confidence_score,
        "tenants": [],
        "spaces": [],
        "property_info": {},
        "content_summary": [],
    }

    # Extract property info
    prop = data.get("property_info") or data.get("property") or {}
    summary["property_info"] = {
        "name": prop.get("name"),
        "address": prop.get("address"),
        "total_sf": prop.get("total_sf") or prop.get("gla_sf"),
        "property_type": prop.get("property_type"),
        "year_built": prop.get("year_built"),
    }

    if summary["property_info"]["name"]:
        summary["content_summary"].append(
            f"Property: {summary['property_info']['name']}"
        )
    if summary["property_info"]["address"]:
        summary["content_summary"].append(
            f"Address: {summary['property_info']['address']}"
        )

    # Extract tenants
    tenants = (
        data.get("existing_tenants")
        or data.get("tenants")
        or data.get("tenant_interest")
        or []
    )
    for t in tenants:
        summary["tenants"].append({
            "name": t.get("name") or t.get("tenant_name") or "Unknown",
            "category": t.get("category"),
            "square_footage": t.get("square_footage"),
            "is_anchor": t.get("is_anchor", False),
            "status": t.get("status"),
        })

    # Extract spaces
    spaces = data.get("available_spaces") or data.get("spaces") or []
    for s in spaces:
        summary["spaces"].append({
            "suite_number": s.get("suite_number") or s.get("name"),
            "square_footage": s.get("square_footage"),
            "asking_rent_psf": s.get("asking_rent_psf"),
            "rent_type": s.get("rent_type"),
        })

    financials = data.get("financials") or {}
    if financials:
        finance_bits: list[str] = []
        if financials.get("total_investment"):
            finance_bits.append(
                f"total investment ${financials['total_investment']:,.0f}"
            )
        if financials.get("noi"):
            finance_bits.append(f"NOI ${financials['noi']:,.0f}")
        if financials.get("irr"):
            finance_bits.append(f"IRR {financials['irr']}%")
        if financials.get("asking_rent_psf"):
            finance_bits.append(
                f"asking rent ${financials['asking_rent_psf']}/SF"
            )
        if finance_bits:
            summary["content_summary"].append(
                "Financials: " + ", ".join(finance_bits)
            )

    demographics = data.get("demographics") or {}
    if demographics:
        demo_bits: list[str] = []
        if demographics.get("radius_miles"):
            demo_bits.append(f"{demographics['radius_miles']}-mile trade area")
        if demographics.get("population"):
            demo_bits.append(f"population {demographics['population']:,}")
        if demographics.get("median_hh_income"):
            demo_bits.append(
                f"median HH income ${demographics['median_hh_income']:,}"
            )
        if demographics.get("traffic_count"):
            demo_bits.append(
                f"traffic {demographics['traffic_count']:,} VPD"
            )
        if demo_bits:
            summary["content_summary"].append(
                "Demographics: " + ", ".join(demo_bits)
            )

    highlights = data.get("highlights") or []
    if highlights:
        summary["content_summary"].append(
            "Highlights: " + "; ".join(highlights[:4])
        )

    timing = data.get("timing") or {}
    if timing:
        timing_bits: list[str] = []
        if timing.get("construction_start"):
            timing_bits.append(f"construction start {timing['construction_start']}")
        if timing.get("delivery_date"):
            timing_bits.append(f"delivery {timing['delivery_date']}")
        if timing.get("lease_up_period"):
            timing_bits.append(f"lease-up {timing['lease_up_period']}")
        if timing_bits:
            summary["content_summary"].append("Timing: " + ", ".join(timing_bits))

    scope_of_work = data.get("scope_of_work")
    if scope_of_work:
        summary["content_summary"].append(f"Scope: {scope_of_work}")

    if summary["tenants"]:
        tenant_preview = []
        for tenant in summary["tenants"][:6]:
          tenant_name = tenant.get("name", "Unknown")
          tenant_status = tenant.get("status")
          if tenant_status:
              tenant_preview.append(f"{tenant_name} ({tenant_status})")
          else:
              tenant_preview.append(tenant_name)
        summary["content_summary"].append(
            "Tenant interest: " + ", ".join(tenant_preview)
        )

    return summary


async def build_project_context(
    db: AsyncSession,
    project_id: str,
) -> dict[str, Any] | None:
    """
    Load project with property + all completed documents, summarize each,
    merge/deduplicate tenants and spaces, and return a structured dict.

    Returns None if project not found or has no useful context.
    """
    result = await db.execute(
        select(Project)
        .options(selectinload(Project.property))
        .where(Project.id == project_id)
    )
    project = result.scalar_one_or_none()
    if not project:
        return None

    # Load all project documents so the assistant can tell the difference
    # between completed context and files that are still processing.
    doc_result = await db.execute(
        select(ParsedDocument)
        .where(
            ParsedDocument.project_id == project_id,
            ParsedDocument.is_archived == False,
        )
        .order_by(ParsedDocument.created_at.desc())
    )
    all_documents = doc_result.scalars().all()
    documents = [
        doc for doc in all_documents
        if doc.status == DocumentStatus.COMPLETED.value
    ]
    processing_documents = [
        doc for doc in all_documents
        if doc.status in {DocumentStatus.PENDING.value, DocumentStatus.PROCESSING.value}
    ]
    failed_documents = [
        doc for doc in all_documents
        if doc.status == DocumentStatus.FAILED.value
    ]

    # Summarize completed documents only.
    doc_summaries = [summarize_extracted_data(d) for d in documents]

    # Merge tenants and spaces across documents, deduplicating by name/suite
    seen_tenants: dict[str, dict] = {}
    all_spaces: list[dict] = []
    seen_suites: set[str] = set()

    for i, summary in enumerate(doc_summaries):
        source_doc = summary["filename"]
        for t in summary["tenants"]:
            key = t["name"].lower().strip()
            if key not in seen_tenants:
                seen_tenants[key] = {**t, "source": source_doc}
        for s in summary["spaces"]:
            suite_key = (s.get("suite_number") or "").lower().strip()
            if suite_key and suite_key not in seen_suites:
                seen_suites.add(suite_key)
                all_spaces.append({**s, "source": source_doc})
            elif not suite_key:
                all_spaces.append({**s, "source": source_doc})

    # Build property info from project's linked property or first completed doc
    prop = project.property
    property_info = {}
    if prop:
        property_info = {
            "name": prop.name,
            "address": f"{prop.address}, {prop.city}, {prop.state} {prop.zip_code}",
            "property_type": prop.property_type,
            "total_sf": prop.total_sf,
        }
    elif doc_summaries:
        # Fall back to first completed document's property info
        property_info = doc_summaries[0].get("property_info", {})

    if not property_info and not all_documents and not project.instructions:
        return None

    context = {
        "project_name": project.name,
        "project_id": project.id,
        "instructions": project.instructions,
        "property": property_info,
        "documents": [
            {
                "filename": s["filename"],
                "document_type": s["document_type"],
                "status": DocumentStatus.COMPLETED.value,
                "confidence_score": s["confidence_score"],
                "processed_at": d.processed_at.isoformat() if d.processed_at else None,
                "tenant_count": len(s["tenants"]),
                "space_count": len(s["spaces"]),
                "content_summary": s["content_summary"],
            }
            for s, d in zip(doc_summaries, documents, strict=False)
        ],
        "processing_documents": [
            {
                "filename": doc.filename,
                "document_type": doc.document_type,
                "status": doc.status,
            }
            for doc in processing_documents
        ],
        "failed_documents": [
            {
                "filename": doc.filename,
                "document_type": doc.document_type,
                "status": doc.status,
                "error_message": doc.error_message,
            }
            for doc in failed_documents
        ],
        "tenants": list(seen_tenants.values()),
        "spaces": all_spaces,
    }

    return context
