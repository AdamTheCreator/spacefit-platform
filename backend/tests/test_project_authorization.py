"""Regression coverage for project ownership at chat and document boundaries."""

import json
import uuid
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from fastapi import BackgroundTasks, HTTPException, UploadFile, WebSocketDisconnect
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import app.db.models  # noqa: F401 - register all ORM relationships
from app.api import chat, documents, projects
from app.db.base import Base
from app.db.models.chat import ChatMessage, ChatSession
from app.db.models.credential import UserPreferences
from app.db.models.deal import Property
from app.db.models.document import ParsedDocument
from app.db.models.import_job import ImportJob
from app.db.models.project import Project
from app.db.models.user import User
from app.services.document_workflow import create_analysis_session_from_document
from app.services.project_context import build_project_context


def uid():
    return str(uuid.uuid4())


@pytest_asyncio.fixture
async def data():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    tables = [
        User.__table__,
        Property.__table__,
        Project.__table__,
        ParsedDocument.__table__,
        ChatSession.__table__,
        ChatMessage.__table__,
        ImportJob.__table__,
        UserPreferences.__table__,
    ]
    async with engine.begin() as conn:
        await conn.run_sync(lambda c: Base.metadata.create_all(c, tables=tables))
        # Only the aggregate fields are needed; the real tsvector is Postgres-only.
        await conn.execute(
            text("CREATE TABLE document_chunks (id TEXT, document_id TEXT)")
        )
    maker = async_sessionmaker(engine, expire_on_commit=False)
    owner, other, project_id = uid(), uid(), uid()
    async with maker() as db:
        db.add_all(
            [
                User(id=owner, email=f"{owner}@test.invalid"),
                User(id=other, email=f"{other}@test.invalid"),
                Project(
                    id=project_id,
                    user_id=owner,
                    name="Private project",
                    instructions="Secret instructions",
                ),
            ]
        )
        await db.commit()
    yield SimpleNamespace(maker=maker, owner=owner, other=other, project=project_id)
    await engine.dispose()


def doc(user_id, project_id, name):
    return ParsedDocument(
        id=uid(),
        user_id=user_id,
        project_id=project_id,
        filename=name,
        file_path="/tmp/test.pdf",
        file_size=10,
        mime_type="application/pdf",
        document_type="leasing_flyer",
        status="completed",
        extracted_data={"property_info": {"name": name}},
    )


@pytest.mark.asyncio
async def test_context_and_project_endpoints_ignore_cross_owner_associations(data):
    async with data.maker() as db:
        db.add_all(
            [
                doc(data.owner, data.project, "owned.pdf"),
                doc(data.other, data.project, "foreign.pdf"),
                ImportJob(
                    id=uid(),
                    user_id=data.owner,
                    project_id=data.project,
                    source="costar",
                    status="ready",
                    original_filename="owned.csv",
                ),
                ImportJob(
                    id=uid(),
                    user_id=data.other,
                    project_id=data.project,
                    source="costar",
                    status="ready",
                    original_filename="foreign.csv",
                ),
                ChatSession(
                    id=uid(), user_id=data.owner, project_id=data.project, title="owned"
                ),
                ChatSession(
                    id=uid(),
                    user_id=data.other,
                    project_id=data.project,
                    title="foreign",
                ),
            ]
        )
        await db.commit()
        assert await build_project_context(db, data.project, data.other) is None
        context = await build_project_context(db, data.project, data.owner)
        assert context["instructions"] == "Secret instructions"
        assert [d["filename"] for d in context["documents"]] == ["owned.pdf"]
        assert [i["filename"] for i in context["imports"]] == ["owned.csv"]
        owner = SimpleNamespace(id=data.owner)
        detail = await projects.get_project(db, owner, data.project)
        assert [d.filename for d in detail.documents] == ["owned.pdf"]
        assert [s.title for s in detail.sessions] == ["owned"]
        assert [
            d.filename
            for d in await projects.list_project_documents(db, owner, data.project)
        ] == ["owned.pdf"]
        assert [
            s.title
            for s in await projects.list_project_sessions(db, owner, data.project)
        ] == ["owned"]
        sessions = await chat.list_chat_sessions(SimpleNamespace(id=data.other), db)
        assert len(sessions) == 1
        assert sessions[0].project_id is None and sessions[0].project_name is None


@pytest.mark.asyncio
async def test_document_upload_rejects_foreign_and_unknown_project_before_writing(
    data, tmp_path, monkeypatch
):
    monkeypatch.setattr(documents, "ensure_upload_dir", lambda: tmp_path)
    async with data.maker() as db:
        for project_id in (data.project, uid()):
            with pytest.raises(HTTPException) as exc:
                await documents.upload_document(
                    db,
                    SimpleNamespace(id=data.other),
                    BackgroundTasks(),
                    UploadFile(file=BytesIO(b"pdf"), filename="test.pdf"),
                    None,
                    project_id,
                    None,
                )
            assert exc.value.status_code == 404
        assert list(tmp_path.iterdir()) == []
        assert (await db.execute(select(ParsedDocument))).scalars().all() == []
        result = await documents.upload_document(
            db,
            SimpleNamespace(id=data.owner),
            BackgroundTasks(),
            UploadFile(file=BytesIO(b"pdf"), filename="test.pdf"),
            None,
            data.project,
            None,
        )
        saved = await db.get(ParsedDocument, str(result.id))
        assert saved.project_id == data.project


@pytest.mark.asyncio
async def test_analysis_does_not_inherit_legacy_cross_owner_project(data):
    async with data.maker() as db:
        foreign = doc(data.other, data.project, "foreign.pdf")
        owned = doc(data.owner, data.project, "owned.pdf")
        db.add_all([foreign, owned])
        await db.commit()
        foreign_session = await create_analysis_session_from_document(
            foreign, data.other, db
        )
        owned_session = await create_analysis_session_from_document(
            owned, data.owner, db
        )
        assert foreign_session.project_id is None
        assert owned_session.project_id == data.project


class Socket:
    def __init__(self, payload, stop_at=None):
        self.payload = json.dumps(payload)
        self.messages = []
        self.stop_at = stop_at

    async def accept(self):
        pass

    async def receive_text(self):
        if self.payload is None:
            raise WebSocketDisconnect()
        payload, self.payload = self.payload, None
        return payload

    async def send_json(self, message):
        self.messages.append(message)
        if message["type"] == self.stop_at:
            raise WebSocketDisconnect()


@pytest_asyncio.fixture
async def socket_env(data, monkeypatch):
    import app.core.database
    import app.services.memory_service
    import app.services.orchestrator

    monkeypatch.setattr(app.core.database, "async_session_factory", data.maker)
    monkeypatch.setattr(
        chat,
        "get_user_from_token",
        AsyncMock(return_value=SimpleNamespace(id=data.other, tier="free")),
    )
    monkeypatch.setattr(chat, "resolve_user_llm", AsyncMock(return_value=None))
    monkeypatch.setattr(
        chat, "_pre_orchestrator_guardrails", lambda *args: (True, None)
    )
    for name in ("classify_message", "check_subscription_limit", "check_token_budget"):
        monkeypatch.setattr(chat, name, AsyncMock(return_value=(True, None)))
    monkeypatch.setattr(
        app.services.memory_service,
        "get_memory_service",
        lambda db: SimpleNamespace(get_context_block=AsyncMock(return_value=None)),
    )
    monkeypatch.setattr(
        app.services.orchestrator,
        "generate_conversation_title",
        AsyncMock(return_value="title"),
    )
    return data


@pytest.mark.asyncio
@pytest.mark.parametrize("scoped", [True, False])
@pytest.mark.parametrize("owned", [True, False])
async def test_websocket_new_session_checks_project(socket_env, scoped, owned):
    data = socket_env
    project_id = data.project
    if owned:
        async with data.maker() as db:
            project = await db.get(Project, project_id)
            project.user_id = data.other
            await db.commit()
    socket = Socket(
        {"content": "hello", "project_id": project_id},
        stop_at="session_info" if scoped else "session_created",
    )
    if scoped:
        await chat.websocket_endpoint(socket, "new", "token")
    else:
        await chat.websocket_chat_endpoint(socket, "token")
    async with data.maker() as db:
        sessions = (await db.execute(select(ChatSession))).scalars().all()
        if owned:
            assert len(sessions) == 1 and sessions[0].project_id == project_id
        else:
            assert sessions == []
            assert any(
                m.get("data", {}).get("content") == "Project not found"
                for m in socket.messages
            )


@pytest.mark.asyncio
async def test_multiplexed_socket_rejects_other_users_session(socket_env, monkeypatch):
    data = socket_env
    session_id = uid()
    async with data.maker() as db:
        db.add(ChatSession(id=session_id, user_id=data.owner, project_id=data.project))
        await db.commit()
    history = AsyncMock()
    monkeypatch.setattr(chat, "load_session_history", history)
    socket = Socket({"session_id": session_id, "content": "hello"})
    await chat.websocket_chat_endpoint(socket, "token")
    assert any(
        m.get("data", {}).get("content") == "Session not found" for m in socket.messages
    )
    history.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("scoped", [True, False])
async def test_websocket_legacy_cross_owner_link_does_not_load_project(
    socket_env, monkeypatch, scoped
):
    import app.services.project_context as context_service

    data = socket_env
    session_id = uid()
    async with data.maker() as db:
        db.add(ChatSession(id=session_id, user_id=data.other, project_id=data.project))
        await db.commit()
    monkeypatch.setattr(chat, "load_session_history", AsyncMock(return_value=[]))
    original = context_service.build_project_context
    results = []

    async def capture_context(db, project_id, user_id):
        result = await original(db, project_id, user_id)
        results.append(result)
        if not scoped:
            raise WebSocketDisconnect()
        return result

    monkeypatch.setattr(context_service, "build_project_context", capture_context)
    socket = Socket(
        {"session_id": session_id, "content": "hello"},
        stop_at="session_info" if scoped else None,
    )
    if scoped:
        await chat.websocket_endpoint(socket, session_id, "token")
    else:
        await chat.websocket_chat_endpoint(socket, "token")
    assert results == [None]


@pytest.mark.asyncio
@pytest.mark.parametrize("scoped", [True, False])
async def test_websocket_can_create_free_form_session(socket_env, scoped):
    socket = Socket(
        {"content": "hello"}, stop_at="session_info" if scoped else "session_created"
    )
    if scoped:
        await chat.websocket_endpoint(socket, "new", "token")
    else:
        await chat.websocket_chat_endpoint(socket, "token")
    async with socket_env.maker() as db:
        sessions = (await db.execute(select(ChatSession))).scalars().all()
        assert len(sessions) == 1 and sessions[0].project_id is None
