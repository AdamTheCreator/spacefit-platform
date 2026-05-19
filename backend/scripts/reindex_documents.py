"""One-shot script to (re-)index every completed parsed_document.

Use cases:
  - Backfilling document_chunks for documents uploaded before Initiative
    5 went live.
  - Re-running the chunker after a chunker change (different target
    tokens, new MIME types supported, etc.).

Idempotent: ``index_document`` deletes the document's existing chunks
before persisting new ones.

Usage:
    backend/.venv/bin/python -m scripts.reindex_documents
    backend/.venv/bin/python -m scripts.reindex_documents --user-id=<uid>
    backend/.venv/bin/python -m scripts.reindex_documents --document-id=<did>

Prints a per-document summary and a final tally.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select  # noqa: E402

from app.core.database import async_session_factory  # noqa: E402
from app.db.models.document import DocumentStatus, ParsedDocument  # noqa: E402
from app.services.document_chunker import index_document  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("reindex")


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--user-id",
        help="Limit reindex to one user (defaults to all users).",
    )
    parser.add_argument(
        "--document-id",
        help="Reindex a single document by id and exit.",
    )
    args = parser.parse_args()

    async with async_session_factory() as db:
        stmt = select(ParsedDocument).where(
            ParsedDocument.status == DocumentStatus.COMPLETED.value,
            ParsedDocument.is_archived == False,  # noqa: E712
        )
        if args.user_id:
            stmt = stmt.where(ParsedDocument.user_id == args.user_id)
        if args.document_id:
            stmt = stmt.where(ParsedDocument.id == args.document_id)

        docs = (await db.execute(stmt)).scalars().all()

    if not docs:
        logger.info("no completed documents to reindex")
        return

    logger.info("reindexing %d documents…", len(docs))
    total_chunks = 0
    failures: list[tuple[str, str]] = []

    for doc in docs:
        # Open a fresh session per document so a single failure can't
        # poison the rest of the run.
        async with async_session_factory() as db:
            try:
                count = await index_document(db, doc.id)
                total_chunks += count
                logger.info(
                    "  %s — %s → %d chunks",
                    doc.id,
                    doc.filename,
                    count,
                )
            except Exception as e:  # noqa: BLE001
                failures.append((doc.id, str(e)))
                logger.warning(
                    "  %s — %s FAILED: %s", doc.id, doc.filename, e
                )

    logger.info("\nreindex complete: %d docs, %d total chunks", len(docs), total_chunks)
    if failures:
        logger.warning("%d documents failed:", len(failures))
        for doc_id, err in failures:
            logger.warning("  %s: %s", doc_id, err)


if __name__ == "__main__":
    asyncio.run(main())
