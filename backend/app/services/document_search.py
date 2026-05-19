"""Postgres-tsvector backed search across a project's document chunks.

Used by the ``document_search`` MCP tool. Kept as a plain async function
so unit tests can call it without spinning up the MCP gateway.

Authorization: every query is filtered by the caller's ``user_id`` —
the denormalized column on ``document_chunks`` makes this a single
indexed b-tree lookup, no joins required. Without a ``user_id`` the
function returns ``[]`` rather than raising; the MCP gateway is what
ought to refuse anonymous calls, this layer just refuses to leak.

Embedding hook: when the ``embedding`` BYTEA column becomes a pgvector
column, swap the tsvector rank for cosine similarity and add a
``query_embedding`` argument. The return shape stays the same so the
tool description and synthesizer behavior don't change.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.document import ParsedDocument
from app.db.models.document_chunk import DocumentChunk

logger = logging.getLogger(__name__)


HARD_LIMIT = 15
DEFAULT_LIMIT = 5
SNIPPET_MAX_CHARS = 320


@dataclass
class SearchHit:
    document_id: str
    filename: str
    page_number: int | None
    chunk_index: int
    snippet: str
    rank: float


async def search_document_chunks(
    db: AsyncSession,
    *,
    query: str,
    project_id: str,
    user_id: str,
    document_id: str | None = None,
    limit: int = DEFAULT_LIMIT,
) -> list[SearchHit]:
    """Return top-N matching chunks for ``query`` within a project.

    Returns ``[]`` (never raises) on empty/unusable inputs so the MCP
    tool can produce a benign user-facing message.
    """
    if not query or not query.strip():
        return []
    if not user_id or not project_id:
        return []

    clamped_limit = max(1, min(HARD_LIMIT, int(limit)))

    ts_query = func.plainto_tsquery("english", query)
    rank = func.ts_rank(DocumentChunk.search_vector, ts_query).label("rank")

    stmt = (
        select(
            DocumentChunk.id,
            DocumentChunk.document_id,
            DocumentChunk.page_number,
            DocumentChunk.chunk_index,
            DocumentChunk.text,
            rank,
            ParsedDocument.filename,
        )
        .join(ParsedDocument, ParsedDocument.id == DocumentChunk.document_id)
        .where(
            DocumentChunk.user_id == user_id,
            DocumentChunk.project_id == project_id,
            DocumentChunk.search_vector.op("@@")(ts_query),
        )
        .order_by(rank.desc(), DocumentChunk.chunk_index.asc())
        .limit(clamped_limit)
    )

    if document_id:
        stmt = stmt.where(DocumentChunk.document_id == document_id)

    try:
        rows = (await db.execute(stmt)).all()
    except Exception as e:
        # tsvector itself is unlikely to fail, but a malformed query
        # (rare with plainto_tsquery, which is permissive) shouldn't
        # blow up the chat — surface a benign empty result instead.
        logger.warning("[doc_search] query=%r failed: %s", query, e)
        return []

    return [
        SearchHit(
            document_id=row.document_id,
            filename=row.filename,
            page_number=row.page_number,
            chunk_index=row.chunk_index,
            snippet=_make_snippet(row.text, query),
            rank=float(row.rank or 0.0),
        )
        for row in rows
    ]


def _make_snippet(text: str, query: str, max_chars: int = SNIPPET_MAX_CHARS) -> str:
    """Center the snippet around the first query-term match.

    Falls back to ``text[:max_chars]`` when no token from the query
    surfaces in the chunk (which can happen with stemming).
    """
    if not text:
        return ""
    lowered = text.lower()
    best = -1
    tokens = [t.lower() for t in re.findall(r"\w+", query) if t]
    for tok in tokens:
        idx = lowered.find(tok)
        if idx != -1 and (best == -1 or idx < best):
            best = idx
    if best < 0:
        return text[:max_chars].strip()

    half = max_chars // 2
    start = max(0, best - half)
    end = min(len(text), start + max_chars)
    if end - start < max_chars:
        start = max(0, end - max_chars)
    snippet = text[start:end].strip()
    prefix = "…" if start > 0 else ""
    suffix = "…" if end < len(text) else ""
    return f"{prefix}{snippet}{suffix}"


def format_hits_for_chat(hits: Sequence[SearchHit]) -> str:
    """Render search results as a markdown block for the LLM to quote.

    Each entry leads with a citation tag the chat surface can later
    promote into a clickable chip (e.g. ``[source:<doc_id>:<page>]``).
    """
    if not hits:
        return (
            "No matching content found in the project's indexed documents. "
            "Either the documents don't mention this topic, or they haven't "
            "been indexed yet."
        )
    lines = [f"## {len(hits)} document_search results"]
    for i, h in enumerate(hits, start=1):
        page = f"p.{h.page_number}" if h.page_number else "page n/a"
        tag = f"[source:{h.document_id}:{h.page_number or 'n/a'}]"
        lines.append(
            f"\n### {i}. {h.filename} — {page} {tag}\n> {h.snippet}"
        )
    lines.append(
        "\nWhen you reference these snippets in your reply, cite by filename + page "
        "(e.g. 'per Greenway-OM.pdf p.4, …') so the user can verify."
    )
    return "\n".join(lines)
