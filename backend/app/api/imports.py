"""Imports API — project-scoped and library upload endpoints for CoStar, Placer, SiteUSA."""

import asyncio
import json
import logging
import os
import uuid
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile, File, status
from pydantic import BaseModel
from sqlalchemy import select

from app.api.deps import CurrentUser, DBSession
from app.core.config import settings
from app.db.models.import_job import ImportJob

logger = logging.getLogger(__name__)

router = APIRouter(tags=["imports"])

ALLOWED_SOURCES = {"costar", "placer", "siteusa"}
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------

class ImportJobResponse(BaseModel):
    id: str
    user_id: str
    project_id: str | None
    source: str
    status: str
    original_filename: str
    record_count: int
    error_message: str | None
    created_at: str

    @classmethod
    def from_model(cls, job: ImportJob) -> "ImportJobResponse":
        return cls(
            id=job.id,
            user_id=job.user_id,
            project_id=job.project_id,
            source=job.source,
            status=job.status,
            original_filename=job.original_filename,
            record_count=job.record_count,
            error_message=job.error_message,
            created_at=job.created_at.isoformat(),
        )


class ImportJobDetailResponse(ImportJobResponse):
    parsed_payload: dict | list | None = None

    @classmethod
    def from_model_full(cls, job: ImportJob) -> "ImportJobDetailResponse":
        parsed = None
        if job.parsed_payload_json:
            try:
                parsed = json.loads(job.parsed_payload_json)
            except json.JSONDecodeError:
                parsed = None
        return cls(
            id=job.id,
            user_id=job.user_id,
            project_id=job.project_id,
            source=job.source,
            status=job.status,
            original_filename=job.original_filename,
            record_count=job.record_count,
            error_message=job.error_message,
            created_at=job.created_at.isoformat(),
            parsed_payload=parsed,
        )


# ---------------------------------------------------------------------------
# Background parse task
# ---------------------------------------------------------------------------

def _ensure_import_dir() -> Path:
    import_path = Path(settings.upload_dir) / "imports"
    import_path.mkdir(parents=True, exist_ok=True)
    return import_path


async def _parse_import_job(job_id: str, source: str, file_path: str) -> None:
    """Background task: parse the uploaded file and update the ImportJob."""
    from app.core.database import async_session_factory

    async with async_session_factory() as db:
        result = await db.execute(select(ImportJob).where(ImportJob.id == job_id))
        job = result.scalar_one_or_none()
        if not job:
            logger.error("Import job %s not found", job_id)
            return

        try:
            if source == "costar":
                from app.services.imports.costar_csv import parse_costar_csv

                with open(file_path, "rb") as f:
                    file_bytes = f.read()
                properties = parse_costar_csv(file_bytes)
                payload = json.dumps([p.model_dump(mode="json") for p in properties])
                record_count = sum(len(p.tenants) for p in properties)

            elif source == "placer":
                from app.services.imports.placer_pdf import parse_placer_pdf

                metrics = await parse_placer_pdf(file_path)
                payload = metrics.model_dump_json()
                record_count = 1  # single trade area report

            elif source == "siteusa":
                from app.services.imports.siteusa_csv import parse_siteusa_csv

                with open(file_path, "rb") as f:
                    file_bytes = f.read()
                records = parse_siteusa_csv(file_bytes)
                payload = json.dumps([r.model_dump(mode="json") for r in records])
                record_count = len(records)

            else:
                raise ValueError(f"Unknown source: {source}")

            job.parsed_payload_json = payload
            job.record_count = record_count
            job.status = "ready"
            logger.info("Import job %s parsed: %d records", job_id, record_count)

        except Exception as e:
            logger.exception("Import job %s failed: %s", job_id, e)
            job.status = "error"
            job.error_message = str(e)[:2000]

        await db.commit()


# ---------------------------------------------------------------------------
# Upload helper
# ---------------------------------------------------------------------------

async def _create_import(
    db,
    user: object,
    source: str,
    file: UploadFile,
    project_id: str | None = None,
) -> ImportJobResponse:
    if source not in ALLOWED_SOURCES:
        raise HTTPException(400, f"Invalid source: {source}. Must be one of {ALLOWED_SOURCES}")

    # Validate file type
    filename = file.filename or "unknown"
    ext = os.path.splitext(filename)[1].lower()
    if source in ("costar", "siteusa") and ext not in (".csv", ".tsv", ".txt"):
        raise HTTPException(400, f"Expected CSV file for {source}, got {ext}")
    if source == "placer" and ext != ".pdf":
        raise HTTPException(400, f"Expected PDF file for Placer, got {ext}")

    # Read and size-check
    contents = await file.read()
    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(400, f"File too large ({len(contents)} bytes). Max is {MAX_FILE_SIZE}.")

    # Save to disk
    import_dir = _ensure_import_dir()
    file_id = uuid.uuid4().hex
    file_path = import_dir / f"{file_id}{ext}"
    file_path.write_bytes(contents)

    # Create DB record
    job = ImportJob(
        user_id=user.id,
        project_id=project_id,
        source=source,
        status="parsing",
        original_filename=filename,
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)

    # Kick off background parse
    asyncio.create_task(_parse_import_job(job.id, source, str(file_path)))

    return ImportJobResponse.from_model(job)


# ---------------------------------------------------------------------------
# Project-scoped endpoints
# ---------------------------------------------------------------------------

@router.post("/projects/{project_id}/imports/{source}")
async def upload_project_import(
    project_id: str,
    source: str,
    db: DBSession,
    user: CurrentUser,
    file: UploadFile = File(...),
) -> ImportJobResponse:
    """Upload a data file scoped to a specific project."""
    # Verify project ownership
    from app.db.models.project import Project

    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.user_id == user.id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(404, "Project not found")

    return await _create_import(db, user, source, file, project_id=project_id)


@router.get("/projects/{project_id}/imports")
async def list_project_imports(
    project_id: str,
    db: DBSession,
    user: CurrentUser,
) -> list[ImportJobResponse]:
    """List imports attached to a project."""
    result = await db.execute(
        select(ImportJob).where(
            ImportJob.user_id == user.id,
            ImportJob.project_id == project_id,
        ).order_by(ImportJob.created_at.desc())
    )
    return [ImportJobResponse.from_model(j) for j in result.scalars()]


# ---------------------------------------------------------------------------
# Library endpoints (project_id = NULL)
# ---------------------------------------------------------------------------

@router.post("/imports/{source}")
async def upload_library_import(
    source: str,
    db: DBSession,
    user: CurrentUser,
    file: UploadFile = File(...),
) -> ImportJobResponse:
    """Upload a data file to the library (not scoped to any project)."""
    return await _create_import(db, user, source, file, project_id=None)


@router.get("/imports")
async def list_library_imports(
    db: DBSession,
    user: CurrentUser,
) -> list[ImportJobResponse]:
    """List library imports (project_id IS NULL) for the current user."""
    result = await db.execute(
        select(ImportJob).where(
            ImportJob.user_id == user.id,
            ImportJob.project_id.is_(None),
        ).order_by(ImportJob.created_at.desc())
    )
    return [ImportJobResponse.from_model(j) for j in result.scalars()]


# ---------------------------------------------------------------------------
# Shared endpoints
# ---------------------------------------------------------------------------

@router.get("/imports/{import_id}")
async def get_import(
    import_id: str,
    db: DBSession,
    user: CurrentUser,
) -> ImportJobDetailResponse:
    """Get full details of an import job including parsed data."""
    result = await db.execute(
        select(ImportJob).where(
            ImportJob.id == import_id,
            ImportJob.user_id == user.id,
        )
    )
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(404, "Import not found")
    return ImportJobDetailResponse.from_model_full(job)


@router.delete("/imports/{import_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_import(
    import_id: str,
    db: DBSession,
    user: CurrentUser,
) -> None:
    """Delete an import job."""
    result = await db.execute(
        select(ImportJob).where(
            ImportJob.id == import_id,
            ImportJob.user_id == user.id,
        )
    )
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(404, "Import not found")
    await db.delete(job)
    await db.commit()


# ---------------------------------------------------------------------------
# Attach / detach (project scoping)
# ---------------------------------------------------------------------------

@router.post(
    "/projects/{project_id}/imports/{import_id}/attach",
    status_code=status.HTTP_200_OK,
)
async def attach_import_to_project(
    project_id: str,
    import_id: str,
    db: DBSession,
    user: CurrentUser,
) -> ImportJobResponse:
    """Attach a library import to a project (overwrites previous attachment)."""
    from app.db.models.project import Project

    # Verify project
    proj_result = await db.execute(
        select(Project).where(Project.id == project_id, Project.user_id == user.id)
    )
    if not proj_result.scalar_one_or_none():
        raise HTTPException(404, "Project not found")

    # Get import
    result = await db.execute(
        select(ImportJob).where(
            ImportJob.id == import_id,
            ImportJob.user_id == user.id,
        )
    )
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(404, "Import not found")

    job.project_id = project_id
    await db.commit()
    await db.refresh(job)
    return ImportJobResponse.from_model(job)


@router.delete(
    "/projects/{project_id}/imports/{import_id}/attach",
    status_code=status.HTTP_200_OK,
)
async def detach_import_from_project(
    project_id: str,
    import_id: str,
    db: DBSession,
    user: CurrentUser,
) -> ImportJobResponse:
    """Detach an import from a project (moves it back to library)."""
    result = await db.execute(
        select(ImportJob).where(
            ImportJob.id == import_id,
            ImportJob.user_id == user.id,
            ImportJob.project_id == project_id,
        )
    )
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(404, "Import not found in this project")

    job.project_id = None
    await db.commit()
    await db.refresh(job)
    return ImportJobResponse.from_model(job)
