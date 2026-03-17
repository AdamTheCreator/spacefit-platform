"""
Document API endpoints for uploading and parsing CRE documents.
"""
import logging
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Body, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload
from pydantic import BaseModel

from app.api.deps import CurrentUser, DBSession
from app.core.config import settings
from app.core.database import async_session_factory

logger = logging.getLogger("document_processing")
from app.db.models.document import (
    AvailableSpace,
    DocumentStatus,
    DocumentType,
    ExistingTenant,
    InvestmentMemo as InvestmentMemoDB,
    ParsedDocument,
    VoidAnalysisResult,
)
from app.models.document import (
    DocumentListResponse,
    DocumentType as PydanticDocumentType,
    DocumentUploadResponse,
    ParsedDocumentDetailResponse,
    ParsedDocumentResponse,
    InvestmentMemoResponse,
    StartAnalysisResponse,
)
from app.services.document_parser import parse_document
from app.services.document_workflow import (
    build_analysis_context,
    create_analysis_session_from_document,
    get_or_create_analysis_session,
)
from app.agents.void_analysis import analyze_voids_for_property, generate_void_report
from app.agents.investment_memo import generate_investment_memo, generate_memo_text

router = APIRouter(prefix="/documents", tags=["documents"])


class DocumentArchiveUpdate(BaseModel):
    is_archived: bool


def ensure_upload_dir() -> Path:
    """Ensure upload directory exists and return path."""
    upload_path = Path(settings.upload_dir)
    upload_path.mkdir(parents=True, exist_ok=True)
    return upload_path


async def process_document_task(
    document_id: str,
    file_path: str,
) -> None:
    """
    Background task to process an uploaded document.

    Note: This runs in a separate context, so we need a new DB session.
    Uses the shared async_session_factory from database.py.
    """
    logger.info("Starting document processing for %s", document_id)

    async with async_session_factory() as session:
        document = None
        try:
            # Get the document
            result = await session.execute(
                select(ParsedDocument).where(ParsedDocument.id == document_id)
            )
            document = result.scalar_one_or_none()

            if not document:
                logger.error("Document %s not found in database", document_id)
                return

            # Update status to processing
            document.status = DocumentStatus.PROCESSING.value
            await session.commit()
            logger.info("Classifying and parsing document %s (%s)", document_id, file_path)

            # Parse the document
            parse_result = await parse_document(file_path)

            # Update document with results
            document.document_type = parse_result["document_type"]
            document.confidence_score = parse_result["confidence"]
            document.extracted_data = parse_result["extracted_data"]
            document.status = DocumentStatus.COMPLETED.value
            document.processed_at = datetime.utcnow()

            # If it's a leasing flyer, create AvailableSpace and ExistingTenant records
            if parse_result["document_type"] == DocumentType.LEASING_FLYER.value:
                extracted = parse_result["extracted_data"]

                # Create available spaces
                for space_data in extracted.get("available_spaces", []):
                    space = AvailableSpace(
                        document_id=document_id,
                        property_id=document.property_id,
                        suite_number=space_data.get("suite_number"),
                        building_address=space_data.get("building_address"),
                        square_footage=space_data.get("square_footage"),
                        min_divisible_sf=space_data.get("min_divisible_sf"),
                        asking_rent_psf=space_data.get("asking_rent_psf"),
                        rent_type=space_data.get("rent_type"),
                        is_endcap=space_data.get("is_endcap", False),
                        is_anchor=space_data.get("is_anchor", False),
                        has_drive_thru=space_data.get("has_drive_thru", False),
                        has_patio=space_data.get("has_patio", False),
                        features=space_data.get("features"),
                        notes=space_data.get("notes"),
                        previous_tenant=space_data.get("previous_tenant"),
                    )
                    session.add(space)

                # Create existing tenants
                for tenant_data in extracted.get("existing_tenants", []):
                    tenant = ExistingTenant(
                        document_id=document_id,
                        property_id=document.property_id,
                        name=tenant_data.get("name", "Unknown"),
                        category=tenant_data.get("category"),
                        suite_number=tenant_data.get("suite_number"),
                        square_footage=tenant_data.get("square_footage"),
                        is_anchor=tenant_data.get("is_anchor", False),
                        is_national=tenant_data.get("is_national", False),
                    )
                    session.add(tenant)

            await session.commit()
            logger.info(
                "Document %s processed successfully: type=%s, confidence=%.2f",
                document_id,
                parse_result["document_type"],
                parse_result["confidence"],
            )

        except Exception as e:
            logger.error("Document %s processing failed: %s", document_id, e, exc_info=True)
            await session.rollback()
            if document is not None:
                document.status = DocumentStatus.FAILED.value
                document.error_message = str(e)[:500]
                await session.commit()
            raise


@router.post("/upload", response_model=DocumentUploadResponse)
async def upload_document(
    db: DBSession,
    current_user: CurrentUser,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    property_id: str | None = Form(None),
    project_id: str | None = Form(None),
    document_type: str | None = Form(None),
) -> DocumentUploadResponse:
    """
    Upload a document (PDF or image) for parsing.

    The document will be processed asynchronously. Use the GET endpoint
    to check the status and retrieve extracted data.

    Supported formats:
    - PDF (.pdf)
    - Images (.png, .jpg, .jpeg, .gif, .webp)
    """
    # Validate file type
    allowed_extensions = {".pdf", ".png", ".jpg", ".jpeg", ".gif", ".webp"}
    file_ext = Path(file.filename or "").suffix.lower()

    if file_ext not in allowed_extensions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type. Allowed: {', '.join(allowed_extensions)}",
        )

    # Check file size
    max_size = settings.max_upload_size_mb * 1024 * 1024
    content = await file.read()
    if len(content) > max_size:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File too large. Maximum size: {settings.max_upload_size_mb}MB",
        )

    # Save file
    upload_dir = ensure_upload_dir()
    file_id = str(uuid.uuid4())
    file_path = upload_dir / f"{file_id}{file_ext}"

    with open(file_path, "wb") as f:
        f.write(content)

    # Determine mime type
    mime_types = {
        ".pdf": "application/pdf",
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".gif": "image/gif",
        ".webp": "image/webp",
    }
    mime_type = mime_types.get(file_ext, "application/octet-stream")

    logger.info(
        "Received upload %s for user=%s project_id=%s property_id=%s",
        file.filename,
        current_user.id,
        project_id,
        property_id,
    )

    # Create document record
    doc_type = DocumentType(document_type) if document_type else DocumentType.OTHER
    document = ParsedDocument(
        user_id=current_user.id,
        property_id=property_id,
        project_id=project_id,
        filename=file.filename or "unknown",
        file_path=str(file_path),
        file_size=len(content),
        mime_type=mime_type,
        document_type=doc_type.value,
        status=DocumentStatus.PENDING.value,
    )

    db.add(document)
    await db.commit()
    await db.refresh(document)

    # Start background processing
    background_tasks.add_task(
        process_document_task,
        document.id,
        str(file_path),
    )

    return DocumentUploadResponse(
        id=document.id,
        filename=document.filename,
        status=DocumentStatus.PENDING,
        message="Document uploaded successfully. Processing will begin shortly.",
    )


@router.get("", response_model=DocumentListResponse)
async def list_documents(
    db: DBSession,
    current_user: CurrentUser,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    document_type: str | None = None,
    status: str | None = None,
    archived: bool = Query(default=False),
) -> DocumentListResponse:
    """List all documents for the current user."""
    query = select(ParsedDocument).where(
        ParsedDocument.user_id == current_user.id,
        ParsedDocument.is_archived == archived,
    )

    if document_type:
        query = query.where(ParsedDocument.document_type == document_type)
    if status:
        query = query.where(ParsedDocument.status == status)

    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Get paginated results
    query = query.order_by(ParsedDocument.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(query)
    documents = result.scalars().all()

    return DocumentListResponse(
        items=[ParsedDocumentResponse.model_validate(doc) for doc in documents],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{document_id}", response_model=ParsedDocumentDetailResponse)
async def get_document(
    document_id: str,
    db: DBSession,
    current_user: CurrentUser,
) -> ParsedDocumentDetailResponse:
    """Get a document with all extracted data."""
    result = await db.execute(
        select(ParsedDocument)
        .options(
            selectinload(ParsedDocument.available_spaces),
            selectinload(ParsedDocument.existing_tenants),
        )
        .where(
            ParsedDocument.id == document_id,
            ParsedDocument.user_id == current_user.id,
        )
    )
    document = result.scalar_one_or_none()

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    return ParsedDocumentDetailResponse.model_validate(document)


@router.get("/{document_id}/file")
async def get_document_file(
    document_id: str,
    db: DBSession,
    current_user: CurrentUser,
):
    """
    Get the actual document file (PDF or image).

    Returns the file with appropriate content type for viewing/downloading.
    """
    from fastapi.responses import FileResponse

    result = await db.execute(
        select(ParsedDocument).where(
            ParsedDocument.id == document_id,
            ParsedDocument.user_id == current_user.id,
        )
    )
    document = result.scalar_one_or_none()

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    if not document.file_path or not os.path.exists(document.file_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document file not found on disk",
        )

    return FileResponse(
        path=document.file_path,
        media_type=document.mime_type,
        filename=document.filename,
    )


@router.delete("/{document_id}")
async def delete_document(
    document_id: str,
    db: DBSession,
    current_user: CurrentUser,
) -> dict:
    """Delete a document and its associated file."""
    result = await db.execute(
        select(ParsedDocument).where(
            ParsedDocument.id == document_id,
            ParsedDocument.user_id == current_user.id,
        )
    )
    document = result.scalar_one_or_none()

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    # Delete the file
    if document.file_path and os.path.exists(document.file_path):
        os.remove(document.file_path)

    # Delete the record
    await db.delete(document)
    await db.commit()

    return {"message": "Document deleted successfully"}


@router.patch("/{document_id}/archive", response_model=ParsedDocumentResponse)
async def archive_document(
    document_id: str,
    data: DocumentArchiveUpdate,
    db: DBSession,
    current_user: CurrentUser,
) -> ParsedDocumentResponse:
    """Archive or restore a document."""
    result = await db.execute(
        select(ParsedDocument).where(
            ParsedDocument.id == document_id,
            ParsedDocument.user_id == current_user.id,
        )
    )
    document = result.scalar_one_or_none()

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    document.is_archived = data.is_archived
    await db.commit()
    await db.refresh(document)
    return ParsedDocumentResponse.model_validate(document)


@router.post("/{document_id}/reprocess")
async def reprocess_document(
    document_id: str,
    db: DBSession,
    current_user: CurrentUser,
    background_tasks: BackgroundTasks,
) -> DocumentUploadResponse:
    """Reprocess a document (useful if parsing failed or needs refresh)."""
    result = await db.execute(
        select(ParsedDocument).where(
            ParsedDocument.id == document_id,
            ParsedDocument.user_id == current_user.id,
        )
    )
    document = result.scalar_one_or_none()

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    if not os.path.exists(document.file_path):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Original file no longer exists",
        )

    # Reset status
    document.status = DocumentStatus.PENDING.value
    document.error_message = None
    document.extracted_data = None
    document.processed_at = None
    await db.commit()

    # Start background processing
    background_tasks.add_task(
        process_document_task,
        document.id,
        document.file_path,
    )

    return DocumentUploadResponse(
        id=document.id,
        filename=document.filename,
        status=DocumentStatus.PENDING,
        message="Document queued for reprocessing.",
    )


# ============================================================================
# Start Analysis Session from Document
# ============================================================================


class StartAnalysisRequest(BaseModel):
    """Optional request body for starting an analysis session."""
    analysis_type: str = "void_analysis"
    trade_area_miles: float = 3.0
    notes: str | None = None


@router.post("/{document_id}/start-analysis", response_model=StartAnalysisResponse)
async def start_analysis_from_document(
    document_id: str,
    db: DBSession,
    current_user: CurrentUser,
    body: StartAnalysisRequest | None = None,
) -> StartAnalysisResponse:
    """
    Start a void analysis session from a parsed document.

    This endpoint:
    1. Validates the document is parsed and has extractable data
    2. Extracts property address, tenants, and available spaces
    3. Creates a new chat session pre-seeded with document context
    4. Returns session ID for frontend to connect via WebSocket

    The created session will have document_context populated with all
    extracted data, allowing immediate void analysis without re-entering
    property information.

    Accepts optional body with analysis_type, trade_area_miles, notes.
    """
    request_body = body or StartAnalysisRequest()

    # Fetch document with ownership check
    result = await db.execute(
        select(ParsedDocument).where(
            ParsedDocument.id == document_id,
            ParsedDocument.user_id == current_user.id,
        )
    )
    document = result.scalar_one_or_none()

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    # Validate document is processed
    if document.status != DocumentStatus.COMPLETED.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Document is not ready for analysis. Current status: {document.status}",
        )

    if not document.extracted_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Document has no extracted data. Please reprocess the document.",
        )

    # Check if document type supports analysis
    supported_types = [
        DocumentType.LEASING_FLYER.value,
        DocumentType.SITE_PLAN.value,
        DocumentType.INVESTMENT_MEMO.value,
        DocumentType.OFFERING_MEMORANDUM.value,
    ]
    if document.document_type not in supported_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Document type '{document.document_type}' does not support void analysis. "
                   f"Supported types: {', '.join(supported_types)}",
        )

    # Get or create analysis session
    session = await get_or_create_analysis_session(
        document_id=document_id,
        user_id=current_user.id,
        db=db,
        analysis_type=request_body.analysis_type,
        trade_area_miles=request_body.trade_area_miles,
        notes=request_body.notes,
    )

    if not session:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create analysis session",
        )

    # Build context for response
    context = build_analysis_context(document)

    return StartAnalysisResponse(
        session_id=session.id,
        property_address=context.full_address,
        property_name=context.property_name,
        tenant_count=len(context.existing_tenants),
        available_space_count=len(context.available_spaces),
        document_type=PydanticDocumentType(document.document_type),
        message=f"Analysis session created. {len(context.existing_tenants)} tenants and "
                f"{len(context.available_spaces)} available spaces extracted from document.",
    )


# ============================================================================
# Void Analysis Endpoints
# ============================================================================


class VoidAnalysisRequest(BaseModel):
    address: str
    radius_miles: float = 3.0
    existing_tenants: list[dict] | None = None
    demographics: dict | None = None


class VoidAnalysisResponse(BaseModel):
    id: str | None = None
    address: str
    radius_miles: float
    total_voids: int
    high_priority_voids: list[str]
    results: dict


@router.post("/analyze/voids", response_model=VoidAnalysisResponse)
async def run_void_analysis(
    db: DBSession,
    current_user: CurrentUser,
    request: VoidAnalysisRequest,
) -> VoidAnalysisResponse:
    """
    Run a void analysis for an address.

    Returns identified gaps in tenant categories based on demographics
    and existing tenant mix.
    """
    try:
        results = await analyze_voids_for_property(
            address=request.address,
            existing_tenants=request.existing_tenants,
            demographics=request.demographics,
            radius_miles=request.radius_miles,
        )

        # Calculate summary metrics
        summary = results.get("summary", {})
        total_voids = summary.get("total_voids", 0)
        high_priority = summary.get("high_priority", [])

        # Save to database
        void_result = VoidAnalysisResult(
            user_id=current_user.id,
            radius_miles=request.radius_miles,
            results=results,
            total_voids=total_voids,
            high_priority_voids=len(high_priority),
        )
        db.add(void_result)
        await db.commit()
        await db.refresh(void_result)

        return VoidAnalysisResponse(
            id=void_result.id,
            address=request.address,
            radius_miles=request.radius_miles,
            total_voids=total_voids,
            high_priority_voids=high_priority,
            results=results,
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to run void analysis: {str(e)}",
        )


@router.get("/analyze/voids/{address:path}")
async def get_void_analysis_quick(
    address: str,
    current_user: CurrentUser,
    radius_miles: float = Query(default=3.0),
) -> dict:
    """
    Quick void analysis endpoint - returns formatted text report.
    """
    try:
        report = await generate_void_report(
            property_address=address,
            radius_miles=radius_miles,
        )
        return {"address": address, "report": report}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate void report: {str(e)}",
        )


# ============================================================================
# Investment Memo Endpoints
# ============================================================================


class InvestmentMemoRequest(BaseModel):
    title: str
    property_info: dict
    demographics: dict | None = None
    tenant_roster: list[dict] | None = None
    void_analysis: dict | None = None
    financials: dict | None = None
    additional_notes: str | None = None


class InvestmentMemoCreateResponse(BaseModel):
    id: str
    title: str
    content: dict
    text_format: str


@router.post("/memos/generate", response_model=InvestmentMemoCreateResponse)
async def generate_investment_memo_endpoint(
    db: DBSession,
    current_user: CurrentUser,
    request: InvestmentMemoRequest,
) -> InvestmentMemoCreateResponse:
    """
    Generate an investment memo from provided data.

    Returns structured memo content and formatted text.
    """
    try:
        # Generate memo content
        memo_content = await generate_investment_memo(
            property_info=request.property_info,
            demographics=request.demographics,
            tenant_roster=request.tenant_roster,
            void_analysis=request.void_analysis,
            financials=request.financials,
            additional_notes=request.additional_notes,
        )

        # Generate text format
        text_format = await generate_memo_text(
            property_info=request.property_info,
            demographics=request.demographics,
            tenant_roster=request.tenant_roster,
            void_analysis=request.void_analysis,
            financials=request.financials,
            additional_notes=request.additional_notes,
        )

        # Save to database
        memo = InvestmentMemoDB(
            user_id=current_user.id,
            title=request.title,
            summary=memo_content.get("executive_summary"),
            location_highlights={"highlights": memo_content.get("location_highlights", [])},
            financials=memo_content.get("investment_highlights"),
            demographics=memo_content.get("demographics_summary"),
            tenant_interest=memo_content.get("tenant_summary"),
            scope_of_work=memo_content.get("opportunity_analysis"),
            is_draft=True,
        )
        db.add(memo)
        await db.commit()
        await db.refresh(memo)

        return InvestmentMemoCreateResponse(
            id=memo.id,
            title=request.title,
            content=memo_content,
            text_format=text_format,
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate investment memo: {str(e)}",
        )


@router.get("/memos")
async def list_investment_memos(
    db: DBSession,
    current_user: CurrentUser,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> dict:
    """List all investment memos for the current user."""
    query = select(InvestmentMemoDB).where(
        InvestmentMemoDB.user_id == current_user.id
    ).order_by(InvestmentMemoDB.created_at.desc())

    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Paginate
    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    memos = result.scalars().all()

    return {
        "items": [
            {
                "id": m.id,
                "title": m.title,
                "summary": m.summary,
                "is_draft": m.is_draft,
                "created_at": m.created_at.isoformat(),
                "updated_at": m.updated_at.isoformat(),
            }
            for m in memos
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/memos/{memo_id}")
async def get_investment_memo(
    memo_id: str,
    db: DBSession,
    current_user: CurrentUser,
) -> dict:
    """Get a single investment memo."""
    result = await db.execute(
        select(InvestmentMemoDB).where(
            InvestmentMemoDB.id == memo_id,
            InvestmentMemoDB.user_id == current_user.id,
        )
    )
    memo = result.scalar_one_or_none()

    if not memo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Investment memo not found",
        )

    return {
        "id": memo.id,
        "title": memo.title,
        "summary": memo.summary,
        "location_highlights": memo.location_highlights,
        "financials": memo.financials,
        "demographics": memo.demographics,
        "tenant_interest": memo.tenant_interest,
        "scope_of_work": memo.scope_of_work,
        "is_draft": memo.is_draft,
        "created_at": memo.created_at.isoformat(),
        "updated_at": memo.updated_at.isoformat(),
    }


@router.delete("/memos/{memo_id}")
async def delete_investment_memo(
    memo_id: str,
    db: DBSession,
    current_user: CurrentUser,
) -> dict:
    """Delete an investment memo."""
    result = await db.execute(
        select(InvestmentMemoDB).where(
            InvestmentMemoDB.id == memo_id,
            InvestmentMemoDB.user_id == current_user.id,
        )
    )
    memo = result.scalar_one_or_none()

    if not memo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Investment memo not found",
        )

    await db.delete(memo)
    await db.commit()

    return {"message": "Investment memo deleted successfully"}


# ============================================================================
# Comprehensive Property Analysis Endpoints
# ============================================================================


class PropertyAnalysisRequest(BaseModel):
    """Request for comprehensive property analysis."""
    document_id: str | None = None
    property_info: dict | None = None
    include_demographics: bool = True
    include_competitors: bool = True
    include_void_analysis: bool = True
    include_memo: bool = False
    radius_miles: float = 3.0


class PropertyAnalysisResponse(BaseModel):
    """Response from comprehensive property analysis."""
    success: bool
    property_address: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    demographics: dict | None = None
    competitors: list[dict] | None = None
    void_analysis: dict | None = None
    investment_memo: dict | None = None
    errors: list[str] | None = None


@router.post("/{document_id}/analyze", response_model=PropertyAnalysisResponse)
async def analyze_document_endpoint(
    document_id: str,
    db: DBSession,
    current_user: CurrentUser,
    include_demographics: bool = Query(default=True),
    include_competitors: bool = Query(default=True),
    include_void_analysis: bool = Query(default=True),
    include_memo: bool = Query(default=False),
    radius_miles: float = Query(default=3.0),
) -> PropertyAnalysisResponse:
    """
    Run comprehensive analysis on an uploaded document.

    This endpoint:
    1. Extracts property info and tenants from the parsed document
    2. Geocodes the property address
    3. Pulls real demographics from Census API
    4. Searches for competitors via Google Places
    5. Runs void analysis with all real data
    6. Optionally generates an investment memo

    This is the proper way to analyze a property from an uploaded flyer.
    """
    from app.services.property_analysis import (
        analyze_document,
        extract_property_context_from_document,
    )

    # Verify document ownership
    result = await db.execute(
        select(ParsedDocument).where(
            ParsedDocument.id == document_id,
            ParsedDocument.user_id == current_user.id,
        )
    )
    document = result.scalar_one_or_none()

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    if document.status != DocumentStatus.COMPLETED.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Document has not been processed yet",
        )

    if not document.extracted_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Document has no extracted data",
        )

    try:
        # Run comprehensive analysis
        analysis_result = await analyze_document(
            document_id=document_id,
            db_session=db,
            include_demographics=include_demographics,
            include_competitors=include_competitors,
            include_void_analysis=include_void_analysis,
            radius_miles=radius_miles,
        )

        return PropertyAnalysisResponse(
            success=True,
            property_address=analysis_result.property_context.full_address,
            latitude=analysis_result.property_context.latitude,
            longitude=analysis_result.property_context.longitude,
            demographics=analysis_result.demographics,
            competitors=analysis_result.competitors,
            void_analysis=analysis_result.void_analysis,
            investment_memo=analysis_result.investment_memo,
            errors=analysis_result.errors,
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Analysis failed: {str(e)}",
        )


# ============ LOI GENERATION ============

class LOIGenerateRequest(BaseModel):
    """Request to generate an LOI."""
    property_id: str | None = None
    purchase_price: float
    earnest_money: float
    earnest_money_type: str = "flat"
    due_diligence_days: int = 30
    closing_days: int = 60
    financing_contingency: bool = True
    financing_days: int = 45
    inspection_contingency: bool = True
    title_contingency: bool = True
    buyer_entity: str = ""
    buyer_contact_name: str = ""
    buyer_contact_email: str = ""
    additional_terms: str = ""


@router.post("/generate/loi")
async def generate_loi_endpoint(
    request: LOIGenerateRequest,
    db: DBSession,
    current_user: CurrentUser,
) -> dict:
    """Generate a Letter of Intent document."""
    from app.agents.loi_generator import LOITerms, generate_loi
    from app.db.models.deal import Property

    property_info: dict = {}
    if request.property_id:
        result = await db.execute(
            select(Property).where(
                Property.id == request.property_id,
                Property.user_id == current_user.id,
            )
        )
        prop = result.scalar_one_or_none()
        if prop:
            property_info = {
                "address": prop.address,
                "city": prop.city,
                "state": prop.state,
                "zip_code": prop.zip_code,
                "property_type": prop.property_type,
                "total_sf": prop.total_sf,
                "asking_price": prop.asking_price,
                "cap_rate": prop.cap_rate,
                "noi": prop.noi,
            }

    terms = LOITerms(
        purchase_price=request.purchase_price,
        earnest_money=request.earnest_money,
        earnest_money_type=request.earnest_money_type,
        due_diligence_days=request.due_diligence_days,
        closing_days=request.closing_days,
        financing_contingency=request.financing_contingency,
        financing_days=request.financing_days,
        inspection_contingency=request.inspection_contingency,
        title_contingency=request.title_contingency,
        buyer_entity=request.buyer_entity,
        buyer_contact_name=request.buyer_contact_name,
        buyer_contact_email=request.buyer_contact_email,
        additional_terms=request.additional_terms,
    )

    loi_result = await generate_loi(property_info, terms)
    return loi_result.to_dict()


# ============ PRO FORMA CALCULATOR ============

class ProFormaRequest(BaseModel):
    """Request for pro forma calculation."""
    purchase_price: float
    cap_rate: float
    noi: float
    loan_to_value: float = 70.0
    interest_rate: float = 6.5
    loan_term_years: int = 10
    amortization_years: int = 30
    hold_period_years: int = 5
    exit_cap_rate: float = 7.5
    rent_growth_rate: float = 2.5
    expense_growth_rate: float = 2.0
    vacancy_rate: float = 5.0
    capex_reserve_psf: float = 0.50
    total_sf: int = 0
    closing_costs_pct: float = 2.0


@router.post("/analysis/pro-forma")
async def calculate_pro_forma_endpoint(
    request: ProFormaRequest,
    current_user: CurrentUser,
) -> dict:
    """Calculate a pro forma analysis for a property acquisition."""
    from app.services.pro_forma import ProFormaInputs, calculate_pro_forma

    inputs = ProFormaInputs(
        purchase_price=request.purchase_price,
        cap_rate=request.cap_rate,
        noi=request.noi,
        loan_to_value=request.loan_to_value,
        interest_rate=request.interest_rate,
        loan_term_years=request.loan_term_years,
        amortization_years=request.amortization_years,
        hold_period_years=request.hold_period_years,
        exit_cap_rate=request.exit_cap_rate,
        rent_growth_rate=request.rent_growth_rate,
        expense_growth_rate=request.expense_growth_rate,
        vacancy_rate=request.vacancy_rate,
        capex_reserve_psf=request.capex_reserve_psf,
        total_sf=request.total_sf,
        closing_costs_pct=request.closing_costs_pct,
    )

    result = calculate_pro_forma(inputs)
    return result.to_dict()


# ============= PDF Export =============


class ExportReportRequest(BaseModel):
    property_name: str = ""
    property_address: str = ""
    trade_area_miles: float = 3.0
    current_tenants: list[dict] | None = None
    tenant_gaps: list[dict] | None = None
    recommended_tenants: list[dict] | None = None
    demographics: dict | None = None


@router.post("/export-report")
async def export_tenant_gap_report(
    request: ExportReportRequest,
    _current_user: CurrentUser,
):
    """Generate a PDF report for tenant gap analysis results."""
    from fastapi.responses import Response
    from app.services.report_generator import generate_tenant_gap_report

    pdf_bytes = generate_tenant_gap_report(
        property_name=request.property_name,
        property_address=request.property_address,
        trade_area_miles=request.trade_area_miles,
        current_tenants=request.current_tenants,
        tenant_gaps=request.tenant_gaps,
        recommended_tenants=request.recommended_tenants,
        demographics=request.demographics,
    )

    filename = f"SpaceFit_Report_{request.property_name or 'Property'}.pdf".replace(" ", "_")

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
