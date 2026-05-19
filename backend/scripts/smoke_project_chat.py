"""End-to-end smoke test for the project document Q&A flow.

What this exercises (no live LLM, no uvicorn — pure service-layer):

  1. Create a throwaway project + parsed_document pointing at a fixture
     text file we stash in ``/tmp``.
  2. Run ``index_document`` and verify chunks landed in the DB.
  3. Call ``search_document_chunks`` with a known hit + a known miss,
     assert ranking and ownership filter.
  4. Call ``build_project_context`` and verify the per-doc ``chunk_count``
     propagates.
  5. Verify ``format_project_context_block`` emits the ``document_search``
     hint with the right project_id.
  6. Clean up rows and the /tmp fixture.

Exit code 0 on success, non-zero on any assertion failure.

Usage:
    backend/.venv/bin/python -m scripts.smoke_project_chat
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
import tempfile
import uuid
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import delete  # noqa: E402

from app.core.database import async_session_factory  # noqa: E402
from app.db.models.document import DocumentStatus, DocumentType, ParsedDocument  # noqa: E402
from app.db.models.document_chunk import DocumentChunk  # noqa: E402
from app.db.models.project import Project  # noqa: E402
from app.db.models.user import User  # noqa: E402
from app.services.document_chunker import index_document  # noqa: E402
from app.services.document_search import search_document_chunks  # noqa: E402
from app.services.project_context import build_project_context  # noqa: E402
from app.services.prompt_registry import format_project_context_block  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("smoke")


FIXTURE_TEXT = """\
GREENWAY PLAZA — OFFERING MEMORANDUM

Page 1
The property is a 42,000 SF grocery-anchored shopping center located at
123 Main Street, Tucson, AZ. The center includes a 25,000 SF Trader Joe's
on a 15-year lease.

Page 2
Loan covenants require a 1.25x debt service coverage ratio and prohibit
additional secured debt without lender consent. Annual reporting must be
delivered within 90 days of fiscal year end.

Page 3
CAM charges are billed monthly and trued up annually based on actual
operating expenses. Pro rata share is calculated by leasable area.

Page 4
Parking ratio is 5.2 spaces per 1,000 SF of leasable area. Site plan
attached separately. Two access points on Main Street and one on Oak Avenue.
"""


def _assert(cond: bool, msg: str) -> None:
    if not cond:
        logger.error("FAIL: %s", msg)
        raise SystemExit(2)
    logger.info("  ok: %s", msg)


async def main() -> None:
    user_id = f"smoke-user-{uuid.uuid4().hex[:8]}"
    project_id = f"smoke-proj-{uuid.uuid4().hex[:8]}"
    document_id = f"smoke-doc-{uuid.uuid4().hex[:8]}"

    # Write the fixture file.
    tmpfile = tempfile.NamedTemporaryFile(
        prefix="smoke-doc-", suffix=".txt", delete=False, mode="w"
    )
    tmpfile.write(FIXTURE_TEXT)
    tmpfile.close()
    file_path = tmpfile.name
    logger.info("fixture written to %s", file_path)

    try:
        # --- seed -----------------------------------------------------------
        async with async_session_factory() as db:
            db.add(
                User(
                    id=user_id,
                    email=f"{user_id}@spacegoose.test.invalid",
                    password_hash="x",
                    first_name="Smoke",
                    last_name="Test",
                    is_active=True,
                )
            )
            db.add(
                Project(
                    id=project_id,
                    user_id=user_id,
                    name="Greenway Plaza",
                    instructions=None,
                    is_archived=False,
                )
            )
            db.add(
                ParsedDocument(
                    id=document_id,
                    user_id=user_id,
                    project_id=project_id,
                    filename="Greenway-OM.txt",
                    file_path=file_path,
                    file_size=len(FIXTURE_TEXT),
                    mime_type="text/plain",
                    document_type=DocumentType.OFFERING_MEMORANDUM.value,
                    status=DocumentStatus.COMPLETED.value,
                    processed_at=datetime.utcnow(),
                )
            )
            await db.commit()
        logger.info("seeded user/project/document")

        # --- 1. chunk the document -----------------------------------------
        async with async_session_factory() as db:
            chunk_count = await index_document(db, document_id)
        _assert(chunk_count > 0, f"index_document produced {chunk_count} chunks")

        # --- 2. happy-path search -------------------------------------------
        async with async_session_factory() as db:
            hits = await search_document_chunks(
                db,
                query="loan covenants debt service",
                project_id=project_id,
                user_id=user_id,
            )
        _assert(bool(hits), "search returned at least one hit")
        _assert(
            "covenant" in hits[0].snippet.lower(),
            "top hit mentions covenants",
        )
        _assert(
            hits[0].filename == "Greenway-OM.txt",
            f"top hit is from the right file (got {hits[0].filename!r})",
        )

        # --- 3. miss returns empty ------------------------------------------
        async with async_session_factory() as db:
            empty = await search_document_chunks(
                db,
                query="kombucha brewery startup",
                project_id=project_id,
                user_id=user_id,
            )
        _assert(empty == [], "no-match query returned empty list")

        # --- 4. ownership filter --------------------------------------------
        async with async_session_factory() as db:
            other = await search_document_chunks(
                db,
                query="loan covenants",
                project_id=project_id,
                user_id="not-this-user",
            )
        _assert(other == [], "wrong user_id sees no chunks")

        # --- 5. project_context surfaces chunk_count ------------------------
        async with async_session_factory() as db:
            ctx = await build_project_context(db, project_id)
        _assert(ctx is not None, "build_project_context returned a context")
        assert ctx is not None  # narrow for type checkers
        _assert(
            len(ctx["documents"]) == 1,
            f"context lists exactly one document (got {len(ctx['documents'])})",
        )
        _assert(
            ctx["documents"][0]["chunk_count"] == chunk_count,
            "chunk_count in context matches what index_document persisted",
        )

        # --- 6. prompt block includes the search-tool hint ------------------
        block = format_project_context_block(ctx)
        _assert(
            "document_search" in block,
            "prompt block instructs the LLM to call document_search",
        )
        _assert(
            f'project_id="{project_id}"' in block,
            "prompt block hard-codes the project_id for the tool call",
        )

        logger.info("\nALL SMOKE CHECKS PASSED")
    finally:
        # --- cleanup --------------------------------------------------------
        try:
            os.unlink(file_path)
        except OSError:
            pass
        async with async_session_factory() as db:
            await db.execute(
                delete(DocumentChunk).where(DocumentChunk.user_id == user_id)
            )
            await db.execute(
                delete(ParsedDocument).where(ParsedDocument.user_id == user_id)
            )
            await db.execute(
                delete(Project).where(Project.user_id == user_id)
            )
            await db.execute(delete(User).where(User.id == user_id))
            await db.commit()


if __name__ == "__main__":
    asyncio.run(main())
