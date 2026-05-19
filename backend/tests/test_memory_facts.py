"""Unit tests for the personal-facts memory layer (Initiative 4).

Two surfaces are exercised:

1. ``MemoryService.get_context_block`` — must inject approved facts under
   the right heading, in last-used-first order, capped at 10, and bump
   ``last_used_at`` on every injected fact.
2. The ``/users/me/memory/facts`` REST handlers — ownership enforced,
   correct status transitions, ``approved_at`` stamped on approve.

The tests use stubbed AsyncSession objects (mirroring ``test_ai_config.py``)
so they run in <1s without touching a real database.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from app.api.memory import (
    UserFactResponse,
    _get_owned_fact,
    approve_fact,
    archive_fact,
    list_facts,
    reject_fact,
)
from app.db.models.user_fact import UserFact
from app.services.memory_service import MemoryService


def _make_fact(
    *,
    fact_id: str = "f1",
    user_id: str = "u1",
    text: str = "prefers Texas multifamily",
    category: str = "geography",
    status: str = "pending",
    confidence: float = 0.8,
    last_used_at: datetime | None = None,
    approved_at: datetime | None = None,
) -> UserFact:
    f = UserFact(
        user_id=user_id,
        text=text,
        category=category,
        status=status,
        confidence=confidence,
    )
    f.id = fact_id
    f.created_at = datetime(2026, 5, 1, 12, 0, 0)
    f.updated_at = f.created_at
    f.last_used_at = last_used_at
    f.approved_at = approved_at
    return f


def _stub_db_with_results(*results) -> MagicMock:
    """Return an AsyncSession-like mock whose ``execute`` yields the given results in order.

    Each ``result`` should be the value returned by ``db.execute(...)`` —
    we wrap it in a coroutine via ``AsyncMock``.
    """
    db = MagicMock()
    db.execute = AsyncMock(side_effect=list(results))
    db.commit = AsyncMock()
    db.rollback = AsyncMock()
    db.refresh = AsyncMock()
    return db


# --- MemoryService.get_context_block ---------------------------------------


@pytest.mark.asyncio
async def test_get_context_block_injects_approved_facts_and_bumps_last_used():
    fact_a = _make_fact(
        fact_id="a",
        text="prefers Texas multifamily, $5-15M",
        last_used_at=datetime(2026, 5, 18),
        approved_at=datetime(2026, 5, 10),
        status="approved",
    )
    fact_b = _make_fact(
        fact_id="b",
        text="works the Charlotte trade area",
        last_used_at=None,
        approved_at=datetime(2026, 5, 12),
        status="approved",
    )

    memory_row = SimpleNamespace(
        analyzed_properties=[],
        book_of_business_summary={},
        preferences={},
        total_analyses=0,
    )

    user_memory_result = MagicMock()
    user_memory_result.scalar_one_or_none = MagicMock(return_value=memory_row)

    facts_scalars = MagicMock()
    facts_scalars.all = MagicMock(return_value=[fact_a, fact_b])
    facts_result = MagicMock()
    facts_result.scalars = MagicMock(return_value=facts_scalars)

    db = _stub_db_with_results(user_memory_result, facts_result)
    svc = MemoryService(db)

    block = await svc.get_context_block("u1")

    assert block is not None
    assert "## What you should remember about me" in block
    assert "prefers Texas multifamily, $5-15M" in block
    assert "works the Charlotte trade area" in block
    # last_used_at should have been bumped on both facts so the next
    # call sees a fresh window.
    assert fact_a.last_used_at is not None
    assert fact_b.last_used_at is not None
    assert fact_a.last_used_at > datetime(2026, 5, 18)
    db.commit.assert_awaited()


@pytest.mark.asyncio
async def test_get_context_block_returns_none_when_no_memory_and_no_facts():
    user_memory_result = MagicMock()
    user_memory_result.scalar_one_or_none = MagicMock(return_value=None)

    empty_scalars = MagicMock()
    empty_scalars.all = MagicMock(return_value=[])
    facts_result = MagicMock()
    facts_result.scalars = MagicMock(return_value=empty_scalars)

    db = _stub_db_with_results(user_memory_result, facts_result)
    svc = MemoryService(db)

    assert await svc.get_context_block("u1") is None
    db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_get_context_block_returns_facts_only_when_structured_memory_empty():
    fact = _make_fact(
        fact_id="a",
        text="owns 12 properties in Charlotte",
        status="approved",
        approved_at=datetime(2026, 5, 12),
    )

    user_memory_result = MagicMock()
    user_memory_result.scalar_one_or_none = MagicMock(return_value=None)

    facts_scalars = MagicMock()
    facts_scalars.all = MagicMock(return_value=[fact])
    facts_result = MagicMock()
    facts_result.scalars = MagicMock(return_value=facts_scalars)

    db = _stub_db_with_results(user_memory_result, facts_result)
    svc = MemoryService(db)

    block = await svc.get_context_block("u1")
    assert block is not None
    assert "## What you should remember about me" in block
    assert "owns 12 properties in Charlotte" in block


@pytest.mark.asyncio
async def test_get_context_block_swallows_commit_errors():
    fact = _make_fact(status="approved", approved_at=datetime(2026, 5, 12))

    user_memory_result = MagicMock()
    user_memory_result.scalar_one_or_none = MagicMock(return_value=None)
    facts_scalars = MagicMock()
    facts_scalars.all = MagicMock(return_value=[fact])
    facts_result = MagicMock()
    facts_result.scalars = MagicMock(return_value=facts_scalars)

    db = _stub_db_with_results(user_memory_result, facts_result)
    db.commit = AsyncMock(side_effect=RuntimeError("concurrent update"))
    db.rollback = AsyncMock()

    svc = MemoryService(db)
    block = await svc.get_context_block("u1")

    # We still produced a usable context block — the failed bump should
    # not crash prompt assembly.
    assert block is not None
    assert "## What you should remember about me" in block
    db.rollback.assert_awaited()


# --- REST handlers ---------------------------------------------------------


@pytest.mark.asyncio
async def test_get_owned_fact_returns_row_when_user_matches():
    fact = _make_fact(fact_id="abc", user_id="u1")
    result = MagicMock()
    result.scalar_one_or_none = MagicMock(return_value=fact)
    db = MagicMock()
    db.execute = AsyncMock(return_value=result)

    out = await _get_owned_fact(db, "u1", "abc")
    assert out is fact


@pytest.mark.asyncio
async def test_get_owned_fact_404_when_not_found_or_wrong_user():
    result = MagicMock()
    result.scalar_one_or_none = MagicMock(return_value=None)
    db = MagicMock()
    db.execute = AsyncMock(return_value=result)

    with pytest.raises(HTTPException) as exc:
        await _get_owned_fact(db, "u1", "abc")
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_approve_fact_sets_status_and_stamps_approved_at():
    fact = _make_fact(fact_id="abc", user_id="u1", status="pending")
    result = MagicMock()
    result.scalar_one_or_none = MagicMock(return_value=fact)
    db = MagicMock()
    db.execute = AsyncMock(return_value=result)
    db.commit = AsyncMock()
    db.refresh = AsyncMock()

    current_user = SimpleNamespace(id="u1")
    before = datetime.utcnow()
    response = await approve_fact("abc", current_user, db)  # type: ignore[arg-type]
    after = datetime.utcnow()

    assert response.status == "approved"
    assert fact.status == "approved"
    assert fact.approved_at is not None
    assert before <= fact.approved_at <= after
    db.commit.assert_awaited()


@pytest.mark.asyncio
async def test_reject_fact_sets_status_to_rejected_without_approved_at():
    fact = _make_fact(fact_id="abc", user_id="u1", status="pending")
    result = MagicMock()
    result.scalar_one_or_none = MagicMock(return_value=fact)
    db = MagicMock()
    db.execute = AsyncMock(return_value=result)
    db.commit = AsyncMock()
    db.refresh = AsyncMock()

    response = await reject_fact("abc", SimpleNamespace(id="u1"), db)  # type: ignore[arg-type]
    assert response.status == "rejected"
    assert fact.status == "rejected"
    assert fact.approved_at is None


@pytest.mark.asyncio
async def test_archive_fact_marks_status_archived():
    fact = _make_fact(fact_id="abc", user_id="u1", status="approved")
    result = MagicMock()
    result.scalar_one_or_none = MagicMock(return_value=fact)
    db = MagicMock()
    db.execute = AsyncMock(return_value=result)
    db.commit = AsyncMock()

    await archive_fact("abc", SimpleNamespace(id="u1"), db)  # type: ignore[arg-type]
    assert fact.status == "archived"
    db.commit.assert_awaited()


@pytest.mark.asyncio
async def test_list_facts_with_filter_returns_response_objects():
    facts = [
        _make_fact(fact_id="a", status="pending", text="fact A"),
        _make_fact(fact_id="b", status="pending", text="fact B"),
    ]
    scalars = MagicMock()
    scalars.all = MagicMock(return_value=facts)
    result = MagicMock()
    result.scalars = MagicMock(return_value=scalars)
    db = MagicMock()
    db.execute = AsyncMock(return_value=result)

    rows = await list_facts(SimpleNamespace(id="u1"), db, status_filter="pending")  # type: ignore[arg-type]
    assert [r.id for r in rows] == ["a", "b"]
    assert all(isinstance(r, UserFactResponse) for r in rows)
    assert {r.status for r in rows} == {"pending"}


def test_user_fact_response_from_row_serializes_timestamps():
    fact = _make_fact(
        fact_id="abc",
        last_used_at=datetime(2026, 5, 18, 9, 0, 0),
        approved_at=datetime(2026, 5, 10, 9, 0, 0),
        status="approved",
    )
    resp = UserFactResponse.from_row(fact)
    assert resp.id == "abc"
    assert resp.status == "approved"
    assert resp.last_used_at == "2026-05-18T09:00:00"
    assert resp.approved_at == "2026-05-10T09:00:00"
    # created_at is always present on a row
    assert resp.created_at
