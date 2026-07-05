"""Integration tests for document freshness stamping + ``POST /reindex``.

PG-gated: mirrors the seed/cleanup pattern from ``test_document_search.py``.
Exercises the real chunker (which reads a small text file off disk) and
the real endpoint against the FastAPI ASGI app.
"""

from __future__ import annotations

import os
import tempfile
import uuid
from datetime import datetime, timedelta
from typing import AsyncIterator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, func, select

from app.core.config import settings
from app.core.database import async_session_factory, engine
from app.core.security import create_access_token
from app.db.models.document import DocumentStatus, DocumentType, ParsedDocument
from app.db.models.document_chunk import DocumentChunk
from app.db.models.project import Project
from app.db.models.user import User
from app.main import app
from app.services.document_chunker import index_document

_NEEDS_PG = pytest.mark.skipif(
    "sqlite" in settings.database_url,
    reason="requires Postgres (document_chunks.search_vector is a PG generated column)",
)


SAMPLE_TEXT = (
    "This is a test document used by the document freshness suite. "
    "It contains enough words to yield at least one chunk after the "
    "chunker's minimum length filter. "
    + ("commercial real estate leasing memo " * 40)
)


def _write_temp_text_file(prefix: str) -> str:
    """Write SAMPLE_TEXT to a temp .txt file and return its path."""
    fd, path = tempfile.mkstemp(prefix=f"reindex-{prefix}-", suffix=".txt")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(SAMPLE_TEXT)
    return path


async def _seed_user(db, user_id: str) -> None:
    db.add(
        User(
            id=user_id,
            email=f"{user_id}@spacegoose.test.invalid",
            password_hash="x",
            first_name="Reindex",
            last_name="Test",
            is_active=True,
        )
    )


async def _seed_project(db, project_id: str, user_id: str) -> None:
    db.add(
        Project(
            id=project_id,
            user_id=user_id,
            name=f"Reindex project {project_id}",
            is_archived=False,
        )
    )


async def _seed_document(
    db,
    *,
    doc_id: str,
    user_id: str,
    project_id: str | None,
    file_path: str,
    status: str = DocumentStatus.COMPLETED.value,
) -> None:
    db.add(
        ParsedDocument(
            id=doc_id,
            user_id=user_id,
            project_id=project_id,
            filename=f"{doc_id}.txt",
            file_path=file_path,
            file_size=os.path.getsize(file_path) if os.path.exists(file_path) else 1,
            mime_type="text/plain",
            document_type=DocumentType.OTHER.value,
            status=status,
            processed_at=datetime.utcnow(),
        )
    )


async def _cleanup(user_ids: list[str], file_paths: list[str]) -> None:
    async with async_session_factory() as db:
        await db.execute(
            delete(DocumentChunk).where(DocumentChunk.user_id.in_(user_ids))
        )
        await db.execute(
            delete(ParsedDocument).where(ParsedDocument.user_id.in_(user_ids))
        )
        await db.execute(delete(Project).where(Project.user_id.in_(user_ids)))
        await db.execute(delete(User).where(User.id.in_(user_ids)))
        await db.commit()
    for path in file_paths:
        try:
            if os.path.exists(path):
                os.remove(path)
        except OSError:
            pass


@pytest_asyncio.fixture(loop_scope="module", autouse=True)
async def _rebind_engine_to_module_loop() -> AsyncIterator[None]:
    """Dispose the shared async engine so its pool binds to this module's loop.

    ``test_document_search.py`` uses a function-scoped loop that closes
    before this module runs; without disposing, the engine's connections
    remain tied to that dead loop and the first query here fails with
    ``Task attached to a different loop``.
    """
    await engine.dispose()
    yield
    await engine.dispose()


@pytest_asyncio.fixture(loop_scope="module")
async def api_client() -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


def _auth_headers(user_id: str) -> dict[str, str]:
    token = create_access_token(user_id)  # type: ignore[arg-type]
    return {"Authorization": f"Bearer {token}"}


@_NEEDS_PG
@pytest.mark.asyncio(loop_scope="module")
async def test_index_document_stamps_indexed_at() -> None:
    user_id = f"test-user-stamp-{uuid.uuid4().hex[:8]}"
    project_id = f"test-proj-stamp-{uuid.uuid4().hex[:8]}"
    doc_id = f"test-doc-stamp-{uuid.uuid4().hex[:8]}"
    file_path = _write_temp_text_file("stamp")

    try:
        async with async_session_factory() as db:
            await _seed_user(db, user_id)
            await _seed_project(db, project_id, user_id)
            await _seed_document(
                db,
                doc_id=doc_id,
                user_id=user_id,
                project_id=project_id,
                file_path=file_path,
            )
            await db.commit()

        async with async_session_factory() as db:
            doc_before = (
                await db.execute(
                    select(ParsedDocument).where(ParsedDocument.id == doc_id)
                )
            ).scalar_one()
            assert doc_before.indexed_at is None

        started_at = datetime.utcnow() - timedelta(seconds=1)

        async with async_session_factory() as db:
            chunk_count = await index_document(db, doc_id)
            assert chunk_count > 0

        async with async_session_factory() as db:
            doc_after = (
                await db.execute(
                    select(ParsedDocument).where(ParsedDocument.id == doc_id)
                )
            ).scalar_one()
            assert doc_after.indexed_at is not None
            assert doc_after.indexed_at >= started_at
    finally:
        await _cleanup([user_id], [file_path])


@_NEEDS_PG
@pytest.mark.asyncio(loop_scope="module")
async def test_index_document_is_idempotent() -> None:
    user_id = f"test-user-idem-{uuid.uuid4().hex[:8]}"
    project_id = f"test-proj-idem-{uuid.uuid4().hex[:8]}"
    doc_id = f"test-doc-idem-{uuid.uuid4().hex[:8]}"
    file_path = _write_temp_text_file("idem")

    try:
        async with async_session_factory() as db:
            await _seed_user(db, user_id)
            await _seed_project(db, project_id, user_id)
            await _seed_document(
                db,
                doc_id=doc_id,
                user_id=user_id,
                project_id=project_id,
                file_path=file_path,
            )
            await db.commit()

        async with async_session_factory() as db:
            count_1 = await index_document(db, doc_id)
            rows_1 = (
                await db.execute(
                    select(func.count())
                    .select_from(DocumentChunk)
                    .where(DocumentChunk.document_id == doc_id)
                )
            ).scalar_one()

        async with async_session_factory() as db:
            count_2 = await index_document(db, doc_id)
            rows_2 = (
                await db.execute(
                    select(func.count())
                    .select_from(DocumentChunk)
                    .where(DocumentChunk.document_id == doc_id)
                )
            ).scalar_one()

        assert count_1 > 0
        assert count_1 == count_2
        assert rows_1 == rows_2
        assert rows_1 == count_1
    finally:
        await _cleanup([user_id], [file_path])


@_NEEDS_PG
@pytest.mark.asyncio(loop_scope="module")
async def test_reindex_endpoint_200_for_completed_owned_doc(
    api_client: AsyncClient,
) -> None:
    user_id = f"test-user-ok-{uuid.uuid4().hex[:8]}"
    project_id = f"test-proj-ok-{uuid.uuid4().hex[:8]}"
    doc_id = f"test-doc-ok-{uuid.uuid4().hex[:8]}"
    file_path = _write_temp_text_file("ok")

    try:
        async with async_session_factory() as db:
            await _seed_user(db, user_id)
            await _seed_project(db, project_id, user_id)
            await _seed_document(
                db,
                doc_id=doc_id,
                user_id=user_id,
                project_id=project_id,
                file_path=file_path,
            )
            await db.commit()

        response = await api_client.post(
            f"{settings.api_prefix}/documents/{doc_id}/reindex",
            headers=_auth_headers(user_id),
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["id"] == doc_id
        assert body["indexed_at"] is not None
        assert isinstance(body["chunk_count"], int)
        assert body["chunk_count"] > 0
    finally:
        await _cleanup([user_id], [file_path])


@_NEEDS_PG
@pytest.mark.asyncio(loop_scope="module")
async def test_reindex_endpoint_409_for_non_completed(
    api_client: AsyncClient,
) -> None:
    user_id = f"test-user-409-{uuid.uuid4().hex[:8]}"
    project_id = f"test-proj-409-{uuid.uuid4().hex[:8]}"
    doc_id = f"test-doc-409-{uuid.uuid4().hex[:8]}"
    file_path = _write_temp_text_file("failed")

    try:
        async with async_session_factory() as db:
            await _seed_user(db, user_id)
            await _seed_project(db, project_id, user_id)
            await _seed_document(
                db,
                doc_id=doc_id,
                user_id=user_id,
                project_id=project_id,
                file_path=file_path,
                status=DocumentStatus.FAILED.value,
            )
            await db.commit()

        response = await api_client.post(
            f"{settings.api_prefix}/documents/{doc_id}/reindex",
            headers=_auth_headers(user_id),
        )
        assert response.status_code == 409, response.text
        body = response.json()
        assert body.get("detail")
    finally:
        await _cleanup([user_id], [file_path])


@_NEEDS_PG
@pytest.mark.asyncio(loop_scope="module")
async def test_reindex_endpoint_404_cross_tenant(
    api_client: AsyncClient,
) -> None:
    owner_id = f"test-user-owner-{uuid.uuid4().hex[:8]}"
    other_id = f"test-user-other-{uuid.uuid4().hex[:8]}"
    project_id = f"test-proj-cross-{uuid.uuid4().hex[:8]}"
    doc_id = f"test-doc-cross-{uuid.uuid4().hex[:8]}"
    file_path = _write_temp_text_file("cross")

    try:
        async with async_session_factory() as db:
            await _seed_user(db, owner_id)
            await _seed_user(db, other_id)
            await _seed_project(db, project_id, owner_id)
            await _seed_document(
                db,
                doc_id=doc_id,
                user_id=owner_id,
                project_id=project_id,
                file_path=file_path,
            )
            await db.commit()

        response = await api_client.post(
            f"{settings.api_prefix}/documents/{doc_id}/reindex",
            headers=_auth_headers(other_id),
        )
        assert response.status_code == 404, response.text
    finally:
        await _cleanup([owner_id, other_id], [file_path])
