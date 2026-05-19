"""Integration test for ``search_document_chunks`` (Initiative 5).

Exercises the real Postgres ``tsvector`` path. Skips when the configured
DB is sqlite (tsvector is PG-only).

To keep this stable under pytest-asyncio's auto mode with the
SQLAlchemy async pool tied to the runtime loop, the integration cases
are collapsed into a single test that runs seed → multiple assertions
→ cleanup in one event loop. The smaller, pure-function helpers
(``_make_snippet``, ``format_hits_for_chat``) get their own unit tests
because they don't need a DB.
"""

from __future__ import annotations

import uuid
from datetime import datetime

import pytest
from sqlalchemy import delete

from app.core.config import settings
from app.core.database import async_session_factory
from app.db.models.document import DocumentStatus, DocumentType, ParsedDocument
from app.db.models.document_chunk import DocumentChunk
from app.db.models.project import Project
from app.db.models.user import User
from app.services.document_search import (
    SearchHit,
    _make_snippet,
    format_hits_for_chat,
    search_document_chunks,
)


_NEEDS_PG = pytest.mark.skipif(
    "sqlite" in settings.database_url,
    reason="document_search requires Postgres tsvector",
)


# ---------------------------------------------------------------------------
# Pure-function helpers (no DB)
# ---------------------------------------------------------------------------


def test_make_snippet_centers_on_match():
    text = "x " * 200 + "TARGET PHRASE HERE " + "y " * 200
    snippet = _make_snippet(text, "target", max_chars=80)
    assert "TARGET" in snippet
    assert snippet.startswith("…")


def test_make_snippet_truncates_when_no_match():
    snippet = _make_snippet("a b c d e f g h i j k l m", "missing", max_chars=10)
    assert len(snippet) <= 11  # plus optional ellipsis


def test_format_hits_for_chat_empty():
    out = format_hits_for_chat([])
    assert "No matching content" in out


def test_format_hits_for_chat_includes_citations():
    hits = [
        SearchHit(
            document_id="doc-1",
            filename="OM.pdf",
            page_number=4,
            chunk_index=2,
            snippet="some text",
            rank=0.5,
        )
    ]
    out = format_hits_for_chat(hits)
    assert "OM.pdf" in out
    assert "p.4" in out
    assert "[source:doc-1:4]" in out


# ---------------------------------------------------------------------------
# Postgres integration test (one big async test so the engine + event loop
# stay consistent for the full seed → query → cleanup cycle)
# ---------------------------------------------------------------------------


@_NEEDS_PG
@pytest.mark.asyncio
async def test_search_document_chunks_end_to_end():
    user_a_id = f"test-user-a-{uuid.uuid4().hex[:8]}"
    user_b_id = f"test-user-b-{uuid.uuid4().hex[:8]}"
    project_a_id = f"test-proj-a-{uuid.uuid4().hex[:8]}"
    project_b_id = f"test-proj-b-{uuid.uuid4().hex[:8]}"
    doc_a1_id = f"test-doc-a1-{uuid.uuid4().hex[:8]}"
    doc_a2_id = f"test-doc-a2-{uuid.uuid4().hex[:8]}"
    doc_b_id = f"test-doc-b-{uuid.uuid4().hex[:8]}"

    try:
        # --- seed -----------------------------------------------------------
        async with async_session_factory() as db:
            db.add_all([
                User(
                    id=user_a_id,
                    email=f"{user_a_id}@spacegoose.test.invalid",
                    password_hash="x",
                    first_name="A",
                    last_name="A",
                    is_active=True,
                ),
                User(
                    id=user_b_id,
                    email=f"{user_b_id}@spacegoose.test.invalid",
                    password_hash="x",
                    first_name="B",
                    last_name="B",
                    is_active=True,
                ),
                Project(
                    id=project_a_id,
                    user_id=user_a_id,
                    name="Project A",
                    is_archived=False,
                ),
                Project(
                    id=project_b_id,
                    user_id=user_b_id,
                    name="Project B",
                    is_archived=False,
                ),
            ])
            for doc_id, user_id, project_id, filename in [
                (doc_a1_id, user_a_id, project_a_id, "Greenway-OM.pdf"),
                (doc_a2_id, user_a_id, project_a_id, "Greenway-Site-Plan.pdf"),
                (doc_b_id, user_b_id, project_b_id, "Other-OM.pdf"),
            ]:
                db.add(
                    ParsedDocument(
                        id=doc_id,
                        user_id=user_id,
                        project_id=project_id,
                        filename=filename,
                        file_path=f"/tmp/{doc_id}.pdf",
                        file_size=1,
                        mime_type="application/pdf",
                        document_type=DocumentType.OFFERING_MEMORANDUM.value,
                        status=DocumentStatus.COMPLETED.value,
                        processed_at=datetime.utcnow(),
                    )
                )

            chunk_specs = [
                # doc A1 — the OM
                (doc_a1_id, user_a_id, project_a_id, 1, 0,
                 "The property is a 42,000 SF grocery-anchored shopping center."),
                (doc_a1_id, user_a_id, project_a_id, 1, 1,
                 "Loan covenants require a 1.25x debt service coverage ratio and "
                 "prohibit additional secured debt without lender consent."),
                (doc_a1_id, user_a_id, project_a_id, 2, 2,
                 "CAM charges are billed monthly and trued up annually based on "
                 "actual operating expenses."),
                (doc_a1_id, user_a_id, project_a_id, 3, 3,
                 "Parking ratio is 5.2 spaces per 1,000 SF of leasable area."),
                # doc A2 — the site plan (also mentions parking)
                (doc_a2_id, user_a_id, project_a_id, 1, 0,
                 "Site plan diagram with 220 striped parking spaces and "
                 "two ingress points."),
                # user B's project
                (doc_b_id, user_b_id, project_b_id, 1, 0,
                 "Loan covenants require a 1.30x debt service coverage ratio."),
            ]
            for doc_id, user_id, project_id, page, idx, text in chunk_specs:
                db.add(
                    DocumentChunk(
                        document_id=doc_id,
                        user_id=user_id,
                        project_id=project_id,
                        chunk_index=idx,
                        page_number=page,
                        text=text,
                        token_count=len(text) // 4,
                    )
                )
            await db.commit()

            # --- assertion 1: ranked match against user A's project ----------
            hits = await search_document_chunks(
                db,
                query="loan covenants debt service",
                project_id=project_a_id,
                user_id=user_a_id,
            )
            assert hits, "expected matches for the loan-covenant query"
            assert "covenant" in hits[0].snippet.lower()
            assert hits[0].filename == "Greenway-OM.pdf"
            assert hits[0].page_number == 1

            # --- assertion 2: no-match query returns empty -------------------
            empty = await search_document_chunks(
                db,
                query="kombucha brewery",
                project_id=project_a_id,
                user_id=user_a_id,
            )
            assert empty == []

            # --- assertion 3: cross-tenant isolation -------------------------
            cross = await search_document_chunks(
                db,
                query="loan covenants",
                project_id=project_b_id,
                user_id=user_a_id,
            )
            assert cross == []

            # --- assertion 4: document_id filter scopes -----------------------
            both = await search_document_chunks(
                db,
                query="parking",
                project_id=project_a_id,
                user_id=user_a_id,
                limit=10,
            )
            filenames = {h.filename for h in both}
            assert {"Greenway-OM.pdf", "Greenway-Site-Plan.pdf"}.issubset(filenames)

            scoped = await search_document_chunks(
                db,
                query="parking",
                project_id=project_a_id,
                user_id=user_a_id,
                document_id=doc_a2_id,
                limit=10,
            )
            assert scoped
            assert {h.filename for h in scoped} == {"Greenway-Site-Plan.pdf"}

            # --- assertion 5: limit is clamped to HARD_LIMIT -----------------
            many = await search_document_chunks(
                db,
                query="property loan ratio plan",
                project_id=project_a_id,
                user_id=user_a_id,
                limit=100,
            )
            assert len(many) <= 15

            # --- assertion 6: empty query short-circuits ---------------------
            empty_q = await search_document_chunks(
                db,
                query="",
                project_id="anything",
                user_id="anyone",
            )
            assert empty_q == []

    finally:
        # Always clean up — cascades on ParsedDocument/Project FKs handle the
        # children when we drop the user.
        async with async_session_factory() as db:
            await db.execute(
                delete(DocumentChunk).where(
                    DocumentChunk.user_id.in_([user_a_id, user_b_id])
                )
            )
            await db.execute(
                delete(ParsedDocument).where(
                    ParsedDocument.user_id.in_([user_a_id, user_b_id])
                )
            )
            await db.execute(
                delete(Project).where(
                    Project.user_id.in_([user_a_id, user_b_id])
                )
            )
            await db.execute(
                delete(User).where(User.id.in_([user_a_id, user_b_id]))
            )
            await db.commit()
