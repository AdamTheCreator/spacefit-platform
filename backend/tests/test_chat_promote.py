"""Integration tests for ``POST /chat/sessions/{id}/promote``.

PG-gated: mirrors the seed/cleanup + ASGI client pattern from
``test_document_reindex.py``. Exercises the real endpoint against the
FastAPI app so the "save a free-form chat to a project" flow is pinned.
"""

from __future__ import annotations

import uuid
from typing import AsyncIterator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select

from app.core.config import settings
from app.core.database import async_session_factory, engine
from app.core.security import create_access_token
from app.db.models.chat import ChatSession
from app.db.models.project import Project
from app.db.models.user import User
from app.main import app

_NEEDS_PG = pytest.mark.skipif(
    "sqlite" in settings.database_url,
    reason="requires Postgres",
)


async def _seed_user(db, user_id: str) -> None:
    db.add(
        User(
            id=user_id,
            email=f"{user_id}@spacegoose.test.invalid",
            password_hash="x",
            first_name="Promote",
            last_name="Test",
            is_active=True,
        )
    )


async def _seed_session(db, session_id: str, user_id: str) -> None:
    db.add(ChatSession(id=session_id, user_id=user_id, project_id=None))


async def _seed_project(db, project_id: str, user_id: str, name: str) -> None:
    db.add(Project(id=project_id, user_id=user_id, name=name, is_archived=False))


async def _cleanup(user_ids: list[str]) -> None:
    async with async_session_factory() as db:
        await db.execute(
            delete(ChatSession).where(ChatSession.user_id.in_(user_ids))
        )
        await db.execute(delete(Project).where(Project.user_id.in_(user_ids)))
        await db.execute(delete(User).where(User.id.in_(user_ids)))
        await db.commit()


@pytest_asyncio.fixture(loop_scope="module", autouse=True)
async def _rebind_engine_to_module_loop() -> AsyncIterator[None]:
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
async def test_promote_to_existing_project(api_client: AsyncClient) -> None:
    user_id = f"promote-user-{uuid.uuid4().hex[:8]}"
    session_id = f"promote-sess-{uuid.uuid4().hex[:8]}"
    project_id = f"promote-proj-{uuid.uuid4().hex[:8]}"

    try:
        async with async_session_factory() as db:
            await _seed_user(db, user_id)
            await _seed_session(db, session_id, user_id)
            await _seed_project(db, project_id, user_id, "Camelback Retail Center")
            await db.commit()

        resp = await api_client.post(
            f"/api/v1/chat/sessions/{session_id}/promote",
            json={"project_id": project_id},
            headers=_auth_headers(user_id),
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["project_id"] == project_id
        assert body["project_name"] == "Camelback Retail Center"

        # The link is persisted on the session row.
        async with async_session_factory() as db:
            sess = (
                await db.execute(
                    select(ChatSession).where(ChatSession.id == session_id)
                )
            ).scalar_one()
            assert sess.project_id == project_id
    finally:
        await _cleanup([user_id])


@_NEEDS_PG
@pytest.mark.asyncio(loop_scope="module")
async def test_promote_creates_new_project(api_client: AsyncClient) -> None:
    user_id = f"promote-user-{uuid.uuid4().hex[:8]}"
    session_id = f"promote-sess-{uuid.uuid4().hex[:8]}"

    try:
        async with async_session_factory() as db:
            await _seed_user(db, user_id)
            await _seed_session(db, session_id, user_id)
            await db.commit()

        resp = await api_client.post(
            f"/api/v1/chat/sessions/{session_id}/promote",
            json={
                "new_project": {
                    "name": "Scottsdale strip retail scan",
                    "property_address": "123 Main St, Scottsdale, AZ",
                }
            },
            headers=_auth_headers(user_id),
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["project_name"] == "Scottsdale strip retail scan"
        new_project_id = body["project_id"]
        assert new_project_id

        async with async_session_factory() as db:
            project = (
                await db.execute(
                    select(Project).where(Project.id == new_project_id)
                )
            ).scalar_one()
            assert project.user_id == user_id
            assert project.property_address == "123 Main St, Scottsdale, AZ"
    finally:
        await _cleanup([user_id])


@_NEEDS_PG
@pytest.mark.asyncio(loop_scope="module")
async def test_promote_rejects_empty_payload(api_client: AsyncClient) -> None:
    user_id = f"promote-user-{uuid.uuid4().hex[:8]}"
    session_id = f"promote-sess-{uuid.uuid4().hex[:8]}"

    try:
        async with async_session_factory() as db:
            await _seed_user(db, user_id)
            await _seed_session(db, session_id, user_id)
            await db.commit()

        resp = await api_client.post(
            f"/api/v1/chat/sessions/{session_id}/promote",
            json={},
            headers=_auth_headers(user_id),
        )
        assert resp.status_code == 422, resp.text
    finally:
        await _cleanup([user_id])


@_NEEDS_PG
@pytest.mark.asyncio(loop_scope="module")
async def test_promote_unknown_session_404(api_client: AsyncClient) -> None:
    user_id = f"promote-user-{uuid.uuid4().hex[:8]}"

    try:
        async with async_session_factory() as db:
            await _seed_user(db, user_id)
            await db.commit()

        resp = await api_client.post(
            "/api/v1/chat/sessions/does-not-exist/promote",
            json={"new_project": {"name": "X"}},
            headers=_auth_headers(user_id),
        )
        assert resp.status_code == 404, resp.text
    finally:
        await _cleanup([user_id])
