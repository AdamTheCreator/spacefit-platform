"""Unit tests for the fact-extractor service (Initiative 4).

Focus on the deterministic, pure-Python pieces that don't require a
database or a live LLM:

  * JSON payload parsing handles markdown fences, prose, and malformed
    JSON without raising.
  * Jaccard similarity is sensible enough to suppress near-duplicates.
  * Confidence is clamped to ``[0.0, 1.0]``.
  * Categories outside the allow-list collapse to ``other``.
"""

from __future__ import annotations

import pytest

from app.services.fact_extractor import (
    _jaccard_similarity,
    _parse_fact_payload,
)


def test_parse_handles_plain_json_list():
    raw = '[{"text": "prefers Texas multifamily", "category": "geography", "confidence": 0.9}]'
    facts = _parse_fact_payload(raw)
    assert len(facts) == 1
    assert facts[0]["text"] == "prefers Texas multifamily"
    assert facts[0]["category"] == "geography"
    assert facts[0]["confidence"] == pytest.approx(0.9)


def test_parse_handles_markdown_code_fences():
    raw = """```json
    [
      {"text": "owns 12 properties in Charlotte", "category": "geography", "confidence": 0.7}
    ]
    ```"""
    facts = _parse_fact_payload(raw)
    assert len(facts) == 1
    assert facts[0]["text"].startswith("owns 12 properties")


def test_parse_extracts_list_embedded_in_prose():
    raw = (
        "Here are the facts I extracted:\n"
        '[{"text": "works at Acme Realty", "category": "personal", "confidence": 0.6}]\n'
        "Hope that helps!"
    )
    facts = _parse_fact_payload(raw)
    assert len(facts) == 1
    assert facts[0]["category"] == "personal"


def test_parse_returns_empty_on_garbage():
    assert _parse_fact_payload("I have no idea, sorry.") == []
    assert _parse_fact_payload("") == []
    assert _parse_fact_payload("[not json}") == []


def test_parse_drops_empty_text_and_caps_at_three():
    raw = (
        "["
        '{"text": "", "category": "other"},'
        '{"text": "fact one", "category": "deal_prefs"},'
        '{"text": "fact two", "category": "geography"},'
        '{"text": "fact three", "category": "personal"},'
        '{"text": "fact four", "category": "business_model"}'
        "]"
    )
    facts = _parse_fact_payload(raw)
    assert len(facts) == 3
    assert [f["text"] for f in facts] == ["fact one", "fact two", "fact three"]


def test_parse_normalizes_unknown_category_to_other():
    raw = '[{"text": "x", "category": "horoscope", "confidence": 0.5}]'
    facts = _parse_fact_payload(raw)
    assert facts[0]["category"] == "other"


def test_parse_clamps_confidence():
    raw = (
        "["
        '{"text": "above", "category": "other", "confidence": 1.7},'
        '{"text": "below", "category": "other", "confidence": -0.3}'
        "]"
    )
    facts = _parse_fact_payload(raw)
    assert facts[0]["confidence"] == 1.0
    assert facts[1]["confidence"] == 0.0


def test_jaccard_similarity_detects_near_duplicates():
    a = "prefers Texas multifamily deals between 5M and 15M"
    b = "Prefers Texas multifamily deals between $5M and $15M."
    assert _jaccard_similarity(a, b) > 0.5


def test_jaccard_similarity_distinguishes_unrelated():
    a = "works in Charlotte trade area"
    b = "owns a kombucha startup"
    assert _jaccard_similarity(a, b) < 0.2


def test_jaccard_similarity_handles_empty_inputs():
    assert _jaccard_similarity("", "anything") == 0.0
    assert _jaccard_similarity("anything", "") == 0.0
