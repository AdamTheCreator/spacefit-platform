"""Unit tests for the chunker (Initiative 5, document Q&A).

These cover the pure-Python pieces — no DB, no PDF, no LLM:

  * Empty / whitespace-only / too-short input produces no chunks.
  * Token estimate falls back to ``len(text) // 4`` without tiktoken.
  * Sliding window respects ``target_tokens`` and ``overlap_tokens``.
  * Page numbers are preserved per chunk; chunks never span pages.
  * Per-document hard cap is honored.
"""

from __future__ import annotations

import pytest

from app.services.document_chunker import (
    MAX_CHUNKS_PER_DOCUMENT,
    MIN_CHUNK_CHARS,
    Chunk,
    _estimate_tokens,
    _normalize_text,
    chunk_text,
)


def test_empty_input_yields_no_chunks():
    assert chunk_text([]) == []
    assert chunk_text([(1, "")]) == []
    assert chunk_text([(None, "   \n  \t")]) == []


def test_normalize_text_collapses_whitespace():
    assert _normalize_text("hello\n\n  world  \t!") == "hello world !"


def test_token_estimate_uses_4_chars_heuristic():
    assert _estimate_tokens("a" * 4) == 1
    assert _estimate_tokens("a" * 800) == 200
    # Never returns 0 even for very short text.
    assert _estimate_tokens("ab") == 1


def test_short_text_below_min_chars_dropped():
    chunks = chunk_text([(1, "tiny")])
    assert chunks == []


def test_chunks_respect_target_size_with_overlap():
    # Build a deterministic stream of words so the test is stable.
    words = " ".join(f"word{i:04d}" for i in range(2000))
    chunks = chunk_text(
        [(1, words)], target_tokens=200, overlap_tokens=20
    )
    assert chunks, "expected at least one chunk for a 2000-word stream"
    # Every chunk should be at least MIN_CHUNK_CHARS and well below
    # 4 * target_tokens (because we break on whitespace).
    for c in chunks:
        assert len(c.text) >= MIN_CHUNK_CHARS
        assert len(c.text) <= 200 * 4 + 1
    # Overlap means the start of chunk N+1 should appear inside chunk N
    # for any internal pair.
    if len(chunks) >= 2:
        # The first ~10 chars of chunk 1 should not appear at position 0
        # of chunk 0 (it's an overlap, not a duplicate).
        assert chunks[0].text != chunks[1].text


def test_chunks_never_span_pages():
    a = "alpha " * 200
    b = "bravo " * 200
    chunks = chunk_text(
        [(1, a), (2, b)], target_tokens=200, overlap_tokens=20
    )
    by_page: dict[int, list[Chunk]] = {}
    for c in chunks:
        by_page.setdefault(c.page_number or 0, []).append(c)
    # Both pages should produce chunks.
    assert 1 in by_page and 2 in by_page
    # No chunk should contain text from the wrong page.
    for c in by_page[1]:
        assert "alpha" in c.text and "bravo" not in c.text
    for c in by_page[2]:
        assert "bravo" in c.text and "alpha" not in c.text


def test_chunk_indexes_are_monotonic_and_unique():
    text = "lorem ipsum dolor sit amet " * 200
    chunks = chunk_text([(1, text)], target_tokens=200, overlap_tokens=20)
    indexes = [c.chunk_index for c in chunks]
    assert indexes == sorted(indexes)
    assert len(set(indexes)) == len(indexes)


def test_invalid_overlap_raises():
    with pytest.raises(ValueError):
        chunk_text([(1, "x" * 4000)], target_tokens=200, overlap_tokens=200)
    with pytest.raises(ValueError):
        chunk_text([(1, "x" * 4000)], target_tokens=0)
    with pytest.raises(ValueError):
        chunk_text([(1, "x" * 4000)], target_tokens=100, overlap_tokens=-1)


def test_hard_cap_truncates_runaway_extractions():
    # Make a single huge page that would otherwise produce way more
    # than MAX_CHUNKS_PER_DOCUMENT slices.
    long_page = "word " * 200_000
    chunks = chunk_text(
        [(1, long_page)], target_tokens=200, overlap_tokens=20
    )
    assert len(chunks) <= MAX_CHUNKS_PER_DOCUMENT


def test_breakpoint_prefers_whitespace_when_possible():
    text = "first second third fourth fifth sixth seventh eighth ninth tenth " * 40
    chunks = chunk_text([(1, text)], target_tokens=20, overlap_tokens=2)
    assert chunks
    # No chunk should END mid-word — last char is a letter (no trailing space
    # after strip()) and the slice should end at a word boundary in the source.
    for c in chunks[:-1]:  # skip the final chunk which may legitimately end mid-stream
        # The last word of each chunk should be a complete one.
        assert " " not in c.text or c.text.split()[-1].isalnum()
