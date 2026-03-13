"""
Document Analysis Workflow Service

Bridges parsed documents to void analysis chat sessions.
Creates pre-seeded chat sessions with document context for seamless analysis.
"""
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.chat import ChatSession
from app.db.models.document import ParsedDocument, DocumentType
from app.services.prompt_registry import VOID_ANALYSIS_PROMPT_ID, DEFAULT_PROMPT_ID


@dataclass
class AnalysisContext:
    """Context extracted from a parsed document for void analysis."""
    property_name: str | None
    property_address: str | None
    city: str | None
    state: str | None
    full_address: str | None
    existing_tenants: list[dict]
    available_spaces: list[dict]
    property_info: dict
    document_type: str


def build_analysis_context(document: ParsedDocument) -> AnalysisContext:
    """
    Extract analysis context from a parsed document.

    Works with both LEASING_FLYER and SITE_PLAN document types.
    """
    extracted_data = document.extracted_data or {}
    property_info = extracted_data.get("property_info", {})

    # Build full address from components
    address_parts = []
    if property_info.get("address"):
        address_parts.append(property_info["address"])
    if property_info.get("city"):
        address_parts.append(property_info["city"])
    if property_info.get("state"):
        address_parts.append(property_info["state"])
    if property_info.get("zip_code"):
        address_parts.append(property_info["zip_code"])

    full_address = ", ".join(address_parts) if address_parts else None

    # Extract tenants based on document type
    existing_tenants = []
    if document.document_type == DocumentType.SITE_PLAN.value:
        # Site plans have tenant_locations
        for tenant in extracted_data.get("tenant_locations", []):
            existing_tenants.append({
                "name": tenant.get("name"),
                "category": tenant.get("category"),
                "square_footage": tenant.get("square_footage"),
                "is_anchor": tenant.get("is_anchor", False),
                "is_national": tenant.get("is_national", False),
            })
    else:
        # Leasing flyers have existing_tenants
        for tenant in extracted_data.get("existing_tenants", []):
            existing_tenants.append({
                "name": tenant.get("name"),
                "category": tenant.get("category"),
                "square_footage": tenant.get("square_footage"),
                "is_anchor": tenant.get("is_anchor", False),
                "is_national": tenant.get("is_national", False),
            })

    # Extract available spaces based on document type
    available_spaces = []
    if document.document_type == DocumentType.SITE_PLAN.value:
        # Site plans have available_areas
        for space in extracted_data.get("available_areas", []):
            available_spaces.append({
                "name": space.get("name"),
                "square_footage": space.get("square_footage"),
                "area_type": space.get("area_type"),
                "position_description": space.get("position_description"),
                "notes": space.get("notes"),
            })
    else:
        # Leasing flyers have available_spaces
        for space in extracted_data.get("available_spaces", []):
            available_spaces.append({
                "suite_number": space.get("suite_number"),
                "square_footage": space.get("square_footage"),
                "asking_rent_psf": space.get("asking_rent_psf"),
                "rent_type": space.get("rent_type"),
                "is_endcap": space.get("is_endcap", False),
                "has_drive_thru": space.get("has_drive_thru", False),
                "notes": space.get("notes"),
            })

    return AnalysisContext(
        property_name=property_info.get("name"),
        property_address=property_info.get("address"),
        city=property_info.get("city"),
        state=property_info.get("state"),
        full_address=full_address,
        existing_tenants=existing_tenants,
        available_spaces=available_spaces,
        property_info=property_info,
        document_type=document.document_type,
    )


def generate_session_title(context: AnalysisContext) -> str:
    """Generate a descriptive title for the analysis session."""
    if context.property_name:
        return f"Analysis: {context.property_name}"
    elif context.full_address:
        # Use first part of address for shorter title
        short_addr = context.property_address or context.full_address.split(",")[0]
        return f"Analysis: {short_addr}"
    else:
        return "Property Analysis"


async def create_analysis_session_from_document(
    document: ParsedDocument,
    user_id: str,
    db: AsyncSession,
    analysis_type: str = "void_analysis",
    trade_area_miles: float = 3.0,
    notes: str | None = None,
) -> ChatSession:
    """
    Create a chat session pre-seeded with document context.

    The session will have document_context populated with extracted
    property info, tenants, and available spaces for use in void analysis.
    """
    # Extract context from document
    context = build_analysis_context(document)

    # Build document context dict for the session
    document_context = {
        "property_address": context.full_address,
        "property_name": context.property_name,
        "existing_tenants": context.existing_tenants,
        "available_spaces": context.available_spaces,
        "property_info": context.property_info,
        "document_type": context.document_type,
        "source_document_id": document.id,
        "analysis_type": analysis_type,
        "trade_area_miles": trade_area_miles,
        "notes": notes,
    }

    # Map analysis_type to prompt ID
    prompt_id_map = {
        "void_analysis": VOID_ANALYSIS_PROMPT_ID,
    }
    system_prompt_id = prompt_id_map.get(analysis_type, DEFAULT_PROMPT_ID)

    # Create session with document link and explicit prompt selection
    session = ChatSession(
        user_id=user_id,
        title=generate_session_title(context),
        source_document_id=document.id,
        document_context=document_context,
        analysis_type=analysis_type,
        system_prompt_id=system_prompt_id,
    )
    db.add(session)
    await db.flush()

    # Update document with session link
    document.analysis_session_id = session.id

    await db.commit()
    await db.refresh(session)

    return session


async def get_or_create_analysis_session(
    document_id: str,
    user_id: str,
    db: AsyncSession,
    analysis_type: str = "void_analysis",
    trade_area_miles: float = 3.0,
    notes: str | None = None,
) -> ChatSession | None:
    """
    Get existing analysis session for a document, or create a new one.

    Returns None if document not found or not owned by user.
    """
    # Fetch document
    result = await db.execute(
        select(ParsedDocument).where(
            ParsedDocument.id == document_id,
            ParsedDocument.user_id == user_id,
        )
    )
    document = result.scalar_one_or_none()

    if not document:
        return None

    # Check for existing session
    if document.analysis_session_id:
        session_result = await db.execute(
            select(ChatSession).where(ChatSession.id == document.analysis_session_id)
        )
        existing_session = session_result.scalar_one_or_none()
        if existing_session:
            return existing_session

    # Create new session
    return await create_analysis_session_from_document(
        document, user_id, db,
        analysis_type=analysis_type,
        trade_area_miles=trade_area_miles,
        notes=notes,
    )
