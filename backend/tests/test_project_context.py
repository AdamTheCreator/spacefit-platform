"""Tests for ``build_project_context`` + ``format_project_context_block``.

These were zero-coverage before Initiative 5; the file pins down the
aggregation and prompt-rendering behavior so a regression in either
half stays caught.

We stub the AsyncSession (mirroring ``test_ai_config.py`` and
``test_memory_facts.py``) so the suite stays in-process and doesn't
need a live database.
"""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.db.models.document import DocumentStatus
from app.services.prompt_registry import format_project_context_block
from app.services.project_context import (
    build_project_context,
    summarize_extracted_data,
)


# ---------------------------------------------------------------------------
# summarize_extracted_data
# ---------------------------------------------------------------------------


def _doc(
    *,
    filename: str = "doc.pdf",
    doc_type: str = "leasing_flyer",
    extracted: dict | None = None,
    confidence: float = 0.9,
):
    d = SimpleNamespace(
        id=f"id-{filename}",
        filename=filename,
        document_type=doc_type,
        confidence_score=confidence,
        extracted_data=extracted or {},
        processed_at=datetime(2026, 5, 1, 12, 0, 0),
        status=DocumentStatus.COMPLETED.value,
        is_archived=False,
        user_id="user-1",
        project_id="proj-1",
        created_at=datetime(2026, 5, 1, 11, 0, 0),
        error_message=None,
        mime_type="application/pdf",
        file_path="/tmp/x",
    )
    return d


def test_summarize_extracted_data_pulls_top_fields():
    summary = summarize_extracted_data(
        _doc(
            filename="Greenway-OM.pdf",
            extracted={
                "property_info": {
                    "name": "Greenway Plaza",
                    "address": "123 Main St",
                    "total_sf": 42000,
                    "property_type": "retail",
                },
                "existing_tenants": [
                    {"name": "Trader Joe's", "category": "grocery", "is_anchor": True},
                    {"name": "Chipotle", "category": "QSR"},
                ],
                "available_spaces": [
                    {"suite_number": "101", "square_footage": 2200, "asking_rent_psf": 32},
                ],
                "financials": {"noi": 1_250_000, "asking_rent_psf": 32},
                "demographics": {"radius_miles": 3, "population": 78000},
                "highlights": ["Strong anchor co-tenancy", "Brand-new HVAC"],
            }
        )
    )
    assert summary["property_info"]["name"] == "Greenway Plaza"
    names = [t["name"] for t in summary["tenants"]]
    assert "Trader Joe's" in names and "Chipotle" in names
    assert summary["spaces"][0]["suite_number"] == "101"
    flat_summary = " | ".join(summary["content_summary"])
    assert "Greenway Plaza" in flat_summary
    assert "NOI" in flat_summary
    assert "population" in flat_summary


def test_summarize_extracted_data_handles_empty_doc():
    summary = summarize_extracted_data(_doc(extracted={}))
    assert summary["tenants"] == []
    assert summary["spaces"] == []
    assert summary["content_summary"] == []


# ---------------------------------------------------------------------------
# build_project_context — orchestration with a stubbed DB session
# ---------------------------------------------------------------------------


def _stub_db_with_results(*results) -> MagicMock:
    db = MagicMock()
    db.execute = AsyncMock(side_effect=list(results))
    return db


def _scalar(value):
    """Wrap a value the way ``await db.execute(...).scalar_one_or_none()`` expects."""
    result = MagicMock()
    result.scalar_one_or_none = MagicMock(return_value=value)
    return result


def _scalars(items):
    """Wrap a list the way ``.scalars().all()`` expects."""
    scalars = MagicMock()
    scalars.all = MagicMock(return_value=items)
    result = MagicMock()
    result.scalars = MagicMock(return_value=scalars)
    # build_project_context iterates the result directly for chunk counts;
    # provide ``.all()`` on the top-level mock too.
    result.all = MagicMock(return_value=items)
    return result


@pytest.mark.asyncio
async def test_build_project_context_returns_none_when_project_missing():
    db = _stub_db_with_results(_scalar(None))
    out = await build_project_context(db, "missing-id")
    assert out is None


@pytest.mark.asyncio
async def test_build_project_context_bucketizes_documents_by_status():
    project = SimpleNamespace(
        id="proj-1",
        name="Greenway",
        instructions="be terse",
        property_address=None,
        property=SimpleNamespace(
            name="Greenway Plaza",
            address="123 Main",
            city="Tucson",
            state="AZ",
            zip_code="85705",
            property_type="retail",
            total_sf=42000,
        ),
    )
    completed = _doc(
        filename="OM.pdf",
        extracted={
            "property_info": {"name": "Greenway Plaza", "address": "123 Main"},
            "existing_tenants": [{"name": "Trader Joe's", "is_anchor": True}],
        },
    )
    processing = _doc(filename="SitePlan.pdf")
    processing.status = DocumentStatus.PROCESSING.value
    failed = _doc(filename="Bad.pdf")
    failed.status = DocumentStatus.FAILED.value
    failed.error_message = "could not parse"

    db = _stub_db_with_results(
        _scalar(project),                              # project lookup
        _scalars([completed, processing, failed]),     # all docs
        _scalars([]),                                  # chunk counts: empty
        _scalars([]),                                  # imports
    )
    ctx = await build_project_context(db, "proj-1")

    assert ctx is not None
    assert ctx["project_name"] == "Greenway"
    assert ctx["instructions"] == "be terse"
    assert ctx["property"]["name"] == "Greenway Plaza"
    assert len(ctx["documents"]) == 1
    assert ctx["documents"][0]["filename"] == "OM.pdf"
    assert ctx["documents"][0]["chunk_count"] == 0
    assert len(ctx["processing_documents"]) == 1
    assert ctx["processing_documents"][0]["filename"] == "SitePlan.pdf"
    assert len(ctx["failed_documents"]) == 1
    assert ctx["failed_documents"][0]["error_message"] == "could not parse"
    # Tenant dedupe: one source doc, one tenant.
    assert {t["name"] for t in ctx["tenants"]} == {"Trader Joe's"}


@pytest.mark.asyncio
async def test_build_project_context_dedupes_tenants_across_documents():
    project = SimpleNamespace(
        id="proj-1",
        name="Greenway",
        instructions=None,
        property_address=None,
        property=None,
    )
    doc1 = _doc(
        filename="OM.pdf",
        extracted={
            "existing_tenants": [
                {"name": "Trader Joe's", "category": "grocery"},
                {"name": "Chipotle"},
            ]
        },
    )
    doc2 = _doc(
        filename="Memo.pdf",
        extracted={
            "existing_tenants": [
                # Same tenant, different casing — should NOT duplicate.
                {"name": "trader joe's", "category": "grocery"},
                {"name": "Shake Shack"},
            ]
        },
    )
    db = _stub_db_with_results(
        _scalar(project),
        _scalars([doc1, doc2]),
        _scalars([(doc1.id, 12), (doc2.id, 4)]),
        _scalars([]),
    )
    ctx = await build_project_context(db, "proj-1")
    tenant_names = {t["name"].lower() for t in ctx["tenants"]}
    assert tenant_names == {"trader joe's", "chipotle", "shake shack"}
    # Chunk counts propagate.
    by_filename = {d["filename"]: d["chunk_count"] for d in ctx["documents"]}
    assert by_filename["OM.pdf"] == 12
    assert by_filename["Memo.pdf"] == 4


@pytest.mark.asyncio
async def test_build_project_context_falls_back_to_first_doc_property():
    project = SimpleNamespace(
        id="proj-1",
        name="Greenway",
        instructions=None,
        property_address=None,
        property=None,  # no linked property row
    )
    doc1 = _doc(
        filename="OM.pdf",
        extracted={
            "property_info": {
                "name": "Greenway Plaza",
                "address": "123 Main, Tucson, AZ",
            }
        },
    )
    db = _stub_db_with_results(
        _scalar(project),
        _scalars([doc1]),
        _scalars([]),
        _scalars([]),
    )
    ctx = await build_project_context(db, "proj-1")
    assert ctx["property"]["name"] == "Greenway Plaza"
    assert "Tucson" in ctx["property"]["address"]


@pytest.mark.asyncio
async def test_build_project_context_uses_inline_property_address():
    """A project created from just a free-text address (the "Create new" /
    chat-promotion flow) — no linked Property, no documents — still yields
    context grounded on that address instead of returning None."""
    project = SimpleNamespace(
        id="proj-1",
        name="1842 Boston Post Rd",
        instructions=None,
        property_address="1842 Boston Post Rd, Fairfield, CT",
        property=None,  # no linked property row
    )
    db = _stub_db_with_results(
        _scalar(project),
        _scalars([]),  # no documents
        _scalars([]),  # chunk counts
        _scalars([]),  # imports
    )
    ctx = await build_project_context(db, "proj-1")

    assert ctx is not None, "address-only project must not drop its context"
    assert ctx["property"]["address"] == "1842 Boston Post Rd, Fairfield, CT"
    # Name falls back to the project name when no property name is known.
    assert ctx["property"]["name"] == "1842 Boston Post Rd"

    # And the address flows through to the tool-grounding hint in the prompt.
    block = format_project_context_block(ctx)
    assert "1842 Boston Post Rd, Fairfield, CT" in block


@pytest.mark.asyncio
async def test_build_project_context_prefers_linked_property_over_inline_address():
    """When both a linked Property and a free-text address exist, the linked
    property's structured address wins (the inline field is only a fallback)."""
    project = SimpleNamespace(
        id="proj-1",
        name="Greenway",
        instructions=None,
        property_address="999 Ignored Ave",
        property=SimpleNamespace(
            name="Greenway Plaza",
            address="123 Main",
            city="Tucson",
            state="AZ",
            zip_code="85705",
            property_type="retail",
            total_sf=42000,
        ),
    )
    db = _stub_db_with_results(
        _scalar(project),
        _scalars([]),
        _scalars([]),
        _scalars([]),
    )
    ctx = await build_project_context(db, "proj-1")

    assert ctx["property"]["address"] == "123 Main, Tucson, AZ 85705"
    assert "999 Ignored Ave" not in ctx["property"]["address"]


# ---------------------------------------------------------------------------
# format_project_context_block
# ---------------------------------------------------------------------------


def test_format_project_context_block_includes_address_routing_hint():
    block = format_project_context_block(
        {
            "project_name": "Greenway",
            "project_id": "proj-1",
            "instructions": None,
            "property": {
                "name": "Greenway Plaza",
                "address": "123 Main St, Tucson, AZ",
                "property_type": "retail",
                "total_sf": 42000,
            },
            "documents": [],
            "processing_documents": [],
            "failed_documents": [],
            "tenants": [],
            "spaces": [],
        }
    )
    assert "<project-context>" in block
    assert "Greenway Plaza" in block
    # The address-routing hint must be present so the orchestrator
    # passes the right location to tools.
    assert "123 Main St, Tucson, AZ" in block
    assert "business_search" in block


def test_format_project_context_block_emits_search_tool_hint_when_chunks_exist():
    block = format_project_context_block(
        {
            "project_name": "Greenway",
            "project_id": "proj-1",
            "instructions": None,
            "property": {},
            "documents": [
                {
                    "filename": "OM.pdf",
                    "document_id": "doc-1",
                    "document_type": "offering_memorandum",
                    "status": "completed",
                    "confidence_score": 0.92,
                    "processed_at": "2026-05-01T12:00:00",
                    "tenant_count": 0,
                    "space_count": 0,
                    "chunk_count": 12,
                    "content_summary": ["Property: Greenway Plaza"],
                }
            ],
            "processing_documents": [],
            "failed_documents": [],
            "tenants": [],
            "spaces": [],
        }
    )
    assert "12 searchable text chunks" in block
    assert "document_id=doc-1" in block
    assert "document_search" in block
    assert 'project_id="proj-1"' in block


def test_format_project_context_block_omits_search_hint_when_no_chunks():
    block = format_project_context_block(
        {
            "project_name": "Greenway",
            "project_id": "proj-1",
            "instructions": None,
            "property": {},
            "documents": [
                {
                    "filename": "OM.pdf",
                    "document_id": "doc-1",
                    "document_type": "offering_memorandum",
                    "status": "completed",
                    "confidence_score": 0.92,
                    "processed_at": None,
                    "tenant_count": 0,
                    "space_count": 0,
                    "chunk_count": 0,
                    "content_summary": [],
                }
            ],
            "processing_documents": [],
            "failed_documents": [],
            "tenants": [],
            "spaces": [],
        }
    )
    # When no document has been indexed yet, the search-tool hint should
    # not appear (the LLM would only get "no matches" trying to use it).
    assert "document_search" not in block


def test_format_project_context_block_renders_processing_and_failed_buckets():
    block = format_project_context_block(
        {
            "project_name": "Greenway",
            "project_id": "proj-1",
            "instructions": None,
            "property": {},
            "documents": [],
            "processing_documents": [
                {
                    "filename": "SitePlan.pdf",
                    "document_type": "site_plan",
                    "status": "processing",
                }
            ],
            "failed_documents": [
                {
                    "filename": "Broken.pdf",
                    "document_type": "other",
                    "status": "failed",
                    "error_message": "OCR timeout",
                }
            ],
            "tenants": [],
            "spaces": [],
        }
    )
    assert "SitePlan.pdf" in block
    assert "Documents Still Processing" in block
    assert "Documents With Errors" in block
    assert "OCR timeout" in block
