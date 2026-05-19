"""Text chunker + indexer for project document Q&A.

Pipeline (called from ``document_workflow`` at the end of a successful
parse, and also exposed as a one-shot ``index_document`` for backfills):

  1. ``extract_raw_text(path, mime_type)`` → list of ``(page_number, text)``
     tuples. PDFs use ``pypdf``; plain text / markdown / json are read
     verbatim. Returns ``[]`` on any unrecoverable error (logged but
     never raised) so the caller can fall through to "no chunks".
  2. ``chunk_text(pages, target_tokens=800, overlap=100)`` → list of
     ``Chunk`` dataclasses with token counts and best-effort page numbers.
     Uses ``len(text)//4`` as a tiktoken-free approximation — we never
     want to add a 100MB tokenizer to the runtime image just for this.
  3. ``index_document(db, document_id)`` wipes any prior chunks for the
     document, persists new ones, commits. Idempotent.

Anything in this file must be safe to call on every uploaded document,
including ones we don't yet know how to chunk — it should never block
the parser's COMPLETED transition.
"""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass
from typing import Sequence

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.document import ParsedDocument
from app.db.models.document_chunk import DocumentChunk

logger = logging.getLogger(__name__)


DEFAULT_TARGET_TOKENS = 800
DEFAULT_OVERLAP_TOKENS = 100
# Hard cap so a runaway extraction (e.g. an OCR'd 500-page doc) can't
# fill the row store with junk chunks. Tune up if real corpora need
# more headroom — chat tools will only ever surface top-N anyway.
MAX_CHUNKS_PER_DOCUMENT = 600

# Anything shorter than this after whitespace collapse isn't worth
# storing — usually page numbers, headers, or footer noise.
MIN_CHUNK_CHARS = 40

_WHITESPACE_RUN = re.compile(r"\s+")


@dataclass
class Chunk:
    text: str
    token_count: int
    page_number: int | None
    chunk_index: int


def _estimate_tokens(text: str) -> int:
    """Cheap token estimate (len // 4) — see module docstring."""
    return max(1, len(text) // 4)


def _normalize_text(text: str) -> str:
    return _WHITESPACE_RUN.sub(" ", text).strip()


def extract_raw_text(file_path: str, mime_type: str | None) -> list[tuple[int | None, str]]:
    """Return ``[(page_number, text), ...]`` from a source file.

    Returns ``[]`` (with a logged warning) on any failure — never raises.
    """
    if not file_path or not os.path.exists(file_path):
        logger.warning(
            "[doc_chunker] file_path missing or not on disk: %r", file_path
        )
        return []

    mime = (mime_type or "").lower()
    ext = os.path.splitext(file_path)[1].lower()

    try:
        if mime == "application/pdf" or ext == ".pdf":
            return _extract_pdf(file_path)
        if mime.startswith("text/") or ext in {".txt", ".md", ".markdown", ".csv"}:
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                return [(None, f.read())]
        if ext == ".json":
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                return [(None, f.read())]
        logger.info(
            "[doc_chunker] no text-extraction path for mime=%r ext=%r; skipping",
            mime_type,
            ext,
        )
        return []
    except Exception as e:
        logger.warning(
            "[doc_chunker] extraction failed for %s: %s", file_path, e
        )
        return []


def _extract_pdf(file_path: str) -> list[tuple[int | None, str]]:
    """PDF text extraction via ``pypdf``.

    Returns one ``(page_number, text)`` tuple per page. Pages that yield
    no extractable text (e.g. pure image scans without OCR) are skipped
    rather than emitted as empty strings so the chunker's overlap window
    doesn't drift across silent gaps.
    """
    try:
        from pypdf import PdfReader
    except ImportError:
        logger.warning(
            "[doc_chunker] pypdf not installed — PDF chunking disabled"
        )
        return []

    pages: list[tuple[int | None, str]] = []
    try:
        reader = PdfReader(file_path)
    except Exception as e:
        logger.warning("[doc_chunker] PdfReader open failed: %s", e)
        return []

    for i, page in enumerate(reader.pages, start=1):
        try:
            text = page.extract_text() or ""
        except Exception as e:
            logger.debug("[doc_chunker] page %d extract failed: %s", i, e)
            continue
        normalized = _normalize_text(text)
        if normalized:
            pages.append((i, normalized))
    return pages


def chunk_text(
    pages: Sequence[tuple[int | None, str]],
    target_tokens: int = DEFAULT_TARGET_TOKENS,
    overlap_tokens: int = DEFAULT_OVERLAP_TOKENS,
) -> list[Chunk]:
    """Slice extracted page text into overlapping chunks.

    Constraints (deliberately simple, easy to test):
      - Chunks never span page boundaries — a chunk's ``page_number`` is
        unambiguous, which keeps citations honest.
      - Inside a page, we slide a window of ``target_tokens`` with
        ``overlap_tokens`` of carry-over so a phrase split across the
        boundary still appears in at least one chunk.
      - Chunks shorter than ``MIN_CHUNK_CHARS`` are dropped.
      - Total chunks per document is hard-capped at ``MAX_CHUNKS_PER_DOCUMENT``.
    """
    if target_tokens <= 0:
        raise ValueError("target_tokens must be positive")
    if overlap_tokens < 0 or overlap_tokens >= target_tokens:
        raise ValueError("overlap_tokens must be in [0, target_tokens)")

    # Convert token windows to character windows using the same 4:1 ratio.
    target_chars = target_tokens * 4
    overlap_chars = overlap_tokens * 4

    chunks: list[Chunk] = []
    idx = 0

    for page_number, raw in pages:
        text = _normalize_text(raw)
        if not text:
            continue
        start = 0
        while start < len(text):
            end = min(len(text), start + target_chars)
            # Prefer to break on a whitespace boundary inside the last
            # 200 chars so we don't slice mid-word.
            if end < len(text):
                breakpoint = text.rfind(" ", max(start + 1, end - 200), end)
                if breakpoint > start + MIN_CHUNK_CHARS:
                    end = breakpoint
            piece = text[start:end].strip()
            if len(piece) >= MIN_CHUNK_CHARS:
                chunks.append(
                    Chunk(
                        text=piece,
                        token_count=_estimate_tokens(piece),
                        page_number=page_number,
                        chunk_index=idx,
                    )
                )
                idx += 1
                if idx >= MAX_CHUNKS_PER_DOCUMENT:
                    logger.warning(
                        "[doc_chunker] hit MAX_CHUNKS_PER_DOCUMENT=%d; truncating",
                        MAX_CHUNKS_PER_DOCUMENT,
                    )
                    return chunks
            if end >= len(text):
                break
            start = max(end - overlap_chars, start + 1)

    return chunks


async def index_document(
    db: AsyncSession,
    document_id: str,
    *,
    commit: bool = True,
) -> int:
    """Re-chunk + re-index a single document.

    Returns the number of chunks persisted. Returns ``0`` (with the row
    set committed) when no text can be extracted — that's a successful
    no-op rather than a failure, so the caller doesn't have to special-case
    image-only PDFs.

    Idempotent: any pre-existing chunks for the document are deleted
    before the new ones are inserted.
    """
    doc = (
        await db.execute(
            select(ParsedDocument).where(ParsedDocument.id == document_id)
        )
    ).scalar_one_or_none()

    if doc is None:
        logger.warning("[doc_chunker] document %s not found", document_id)
        return 0

    pages = extract_raw_text(doc.file_path, doc.mime_type)
    new_chunks = chunk_text(pages)

    # Always blow away old chunks first so a re-run isn't additive.
    await db.execute(
        delete(DocumentChunk).where(DocumentChunk.document_id == document_id)
    )

    for c in new_chunks:
        db.add(
            DocumentChunk(
                document_id=document_id,
                user_id=doc.user_id,
                project_id=doc.project_id,
                chunk_index=c.chunk_index,
                page_number=c.page_number,
                text=c.text,
                token_count=c.token_count,
            )
        )

    if commit:
        await db.commit()

    logger.info(
        "[doc_chunker] indexed document=%s chunks=%d pages=%d",
        document_id,
        len(new_chunks),
        len(pages),
    )
    return len(new_chunks)
