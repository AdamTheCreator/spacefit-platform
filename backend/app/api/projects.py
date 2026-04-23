"""
Projects API — CRUD + scoped documents and chat sessions.
"""
import logging
import os

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload
from pydantic import BaseModel

from app.api.deps import CurrentUser, DBSession
from app.db.models.chat import ChatMessage, ChatSession
from app.db.models.document import ParsedDocument
from app.db.models.project import Project
from app.models.document import ParsedDocumentResponse
from app.models.project import (
    ChatSessionBrief,
    ProjectCreate,
    ProjectDetailResponse,
    ProjectListResponse,
    ProjectResponse,
    ProjectUpdate,
)
from app.services.chat_titles import backfill_session_title

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/projects", tags=["projects"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _project_response(project: Project, doc_count: int = 0, session_count: int = 0) -> ProjectResponse:
    return ProjectResponse(
        id=project.id,
        user_id=project.user_id,
        property_id=project.property_id,
        name=project.name,
        description=project.description,
        instructions=project.instructions,
        is_archived=project.is_archived,
        document_count=doc_count,
        session_count=session_count,
        created_at=project.created_at,
        updated_at=project.updated_at,
    )


class ProjectArchiveUpdate(BaseModel):
    is_archived: bool


async def _get_user_project(db, project_id: str, user_id: str) -> Project:
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.user_id == user_id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return project


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------

@router.get("", response_model=ProjectListResponse)
async def list_projects(
    db: DBSession,
    current_user: CurrentUser,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: str | None = Query(None),
    archived: bool = Query(False),
):
    """List the current user's projects with document/session counts."""
    base = select(Project).where(
        Project.user_id == current_user.id,
        Project.is_archived == archived,
    )

    if search:
        base = base.where(Project.name.ilike(f"%{search}%"))

    # Total count
    total_q = select(func.count()).select_from(base.subquery())
    total = (await db.execute(total_q)).scalar() or 0

    # Fetch page
    projects = (
        await db.execute(
            base.order_by(Project.updated_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).scalars().all()

    # Batch-fetch counts
    project_ids = [p.id for p in projects]
    doc_counts: dict[str, int] = {}
    session_counts: dict[str, int] = {}

    if project_ids:
        doc_q = (
            select(ParsedDocument.project_id, func.count())
            .where(ParsedDocument.project_id.in_(project_ids))
            .group_by(ParsedDocument.project_id)
        )
        for pid, cnt in await db.execute(doc_q):
            doc_counts[pid] = cnt

        ses_q = (
            select(ChatSession.project_id, func.count())
            .where(ChatSession.project_id.in_(project_ids))
            .group_by(ChatSession.project_id)
        )
        for pid, cnt in await db.execute(ses_q):
            session_counts[pid] = cnt

    items = [
        _project_response(p, doc_counts.get(p.id, 0), session_counts.get(p.id, 0))
        for p in projects
    ]

    return ProjectListResponse(items=items, total=total, page=page, page_size=page_size)


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    db: DBSession,
    current_user: CurrentUser,
    data: ProjectCreate,
):
    """Create a new project."""
    project = Project(
        user_id=current_user.id,
        property_id=data.property_id,
        name=data.name,
        description=data.description,
        instructions=data.instructions,
        property_address=data.property_address,
        is_archived=False,
    )
    db.add(project)
    await db.commit()
    await db.refresh(project)
    return _project_response(project)


@router.get("/{project_id}", response_model=ProjectDetailResponse)
async def get_project(
    db: DBSession,
    current_user: CurrentUser,
    project_id: str,
):
    """Get project detail with property, documents, and sessions."""
    result = await db.execute(
        select(Project)
        .options(
            selectinload(Project.property),
            selectinload(Project.documents),
            selectinload(Project.sessions).selectinload(ChatSession.messages),
        )
        .where(Project.id == project_id, Project.user_id == current_user.id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    backfilled = False
    for s in project.sessions:
        if backfill_session_title(s):
            backfilled = True
    if backfilled:
        await db.commit()

    # Build session briefs with message counts
    session_briefs = [
        ChatSessionBrief(
            id=s.id,
            title=s.title,
            analysis_type=s.analysis_type,
            message_count=len(s.messages),
            created_at=s.created_at,
            updated_at=s.updated_at,
        )
        for s in project.sessions
    ]

    doc_responses = [ParsedDocumentResponse.model_validate(d) for d in project.documents]

    return ProjectDetailResponse(
        id=project.id,
        user_id=project.user_id,
        property_id=project.property_id,
        name=project.name,
        description=project.description,
        instructions=project.instructions,
        is_archived=project.is_archived,
        document_count=len(project.documents),
        session_count=len(project.sessions),
        created_at=project.created_at,
        updated_at=project.updated_at,
        property=project.property,
        documents=doc_responses,
        sessions=session_briefs,
    )


@router.patch("/{project_id}", response_model=ProjectResponse)
async def update_project(
    db: DBSession,
    current_user: CurrentUser,
    project_id: str,
    data: ProjectUpdate,
):
    """Update a project's name, description, or instructions."""
    project = await _get_user_project(db, project_id, current_user.id)

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(project, field, value)

    await db.commit()
    await db.refresh(project)

    # Fetch counts
    doc_count = (await db.execute(
        select(func.count()).where(ParsedDocument.project_id == project.id)
    )).scalar() or 0
    session_count = (await db.execute(
        select(func.count()).where(ChatSession.project_id == project.id)
    )).scalar() or 0

    return _project_response(project, doc_count, session_count)


@router.patch("/{project_id}/archive", response_model=ProjectResponse)
async def archive_project(
    db: DBSession,
    current_user: CurrentUser,
    project_id: str,
    data: ProjectArchiveUpdate,
):
    """Archive or restore a project."""
    project = await _get_user_project(db, project_id, current_user.id)
    project.is_archived = data.is_archived

    await db.commit()
    await db.refresh(project)

    doc_count = (await db.execute(
        select(func.count()).where(ParsedDocument.project_id == project.id)
    )).scalar() or 0
    session_count = (await db.execute(
        select(func.count()).where(ChatSession.project_id == project.id)
    )).scalar() or 0

    return _project_response(project, doc_count, session_count)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    db: DBSession,
    current_user: CurrentUser,
    project_id: str,
):
    """Delete a project, permanently removing attached documents and unlinking chats."""
    project = await _get_user_project(db, project_id, current_user.id)

    # Delete project documents and their files from disk.
    docs = (await db.execute(
        select(ParsedDocument).where(
            ParsedDocument.project_id == project.id,
            ParsedDocument.user_id == current_user.id,
        )
    )).scalars().all()

    if docs:
        doc_ids = [doc.id for doc in docs]
        sessions_with_source_docs = (
            await db.execute(
                select(ChatSession).where(
                    ChatSession.user_id == current_user.id,
                    ChatSession.source_document_id.in_(doc_ids),
                )
            )
        ).scalars().all()

        for session in sessions_with_source_docs:
            session.source_document_id = None

    for doc in docs:
        if doc.file_path and os.path.exists(doc.file_path):
            os.remove(doc.file_path)
        await db.delete(doc)

    # Keep chat sessions, but detach them from the deleted project.
    sessions = (await db.execute(
        select(ChatSession).where(
            ChatSession.project_id == project.id,
            ChatSession.user_id == current_user.id,
        )
    )).scalars().all()
    for s in sessions:
        s.project_id = None

    await db.delete(project)
    await db.commit()


# ---------------------------------------------------------------------------
# Scoped sub-resources
# ---------------------------------------------------------------------------

@router.get("/{project_id}/documents", response_model=list[ParsedDocumentResponse])
async def list_project_documents(
    db: DBSession,
    current_user: CurrentUser,
    project_id: str,
):
    """List documents belonging to this project."""
    await _get_user_project(db, project_id, current_user.id)

    result = await db.execute(
        select(ParsedDocument)
        .where(
            ParsedDocument.project_id == project_id,
            ParsedDocument.is_archived == False,
        )
        .order_by(ParsedDocument.created_at.desc())
    )
    return [ParsedDocumentResponse.model_validate(d) for d in result.scalars().all()]


@router.get("/{project_id}/sessions", response_model=list[ChatSessionBrief])
async def list_project_sessions(
    db: DBSession,
    current_user: CurrentUser,
    project_id: str,
):
    """List chat sessions belonging to this project."""
    await _get_user_project(db, project_id, current_user.id)

    result = await db.execute(
        select(ChatSession)
        .options(selectinload(ChatSession.messages))
        .where(ChatSession.project_id == project_id)
        .order_by(ChatSession.updated_at.desc())
    )
    sessions = result.scalars().all()

    backfilled = False
    for s in sessions:
        if backfill_session_title(s):
            backfilled = True
    if backfilled:
        await db.commit()

    return [
        ChatSessionBrief(
            id=s.id,
            title=s.title,
            analysis_type=s.analysis_type,
            message_count=len(s.messages),
            created_at=s.created_at,
            updated_at=s.updated_at,
        )
        for s in sessions
    ]


@router.post("/{project_id}/sessions", response_model=ChatSessionBrief, status_code=status.HTTP_201_CREATED)
async def create_project_session(
    db: DBSession,
    current_user: CurrentUser,
    project_id: str,
):
    """Create a new chat session within a project."""
    await _get_user_project(db, project_id, current_user.id)

    session = ChatSession(
        user_id=current_user.id,
        project_id=project_id,
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)

    return ChatSessionBrief(
        id=session.id,
        title=session.title,
        analysis_type=session.analysis_type,
        message_count=0,
        created_at=session.created_at,
        updated_at=session.updated_at,
    )
