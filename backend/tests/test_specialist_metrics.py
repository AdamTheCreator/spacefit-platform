"""Tests for the in-memory specialist metrics counter.

The counters drive the ``GET /admin/metrics/specialists`` endpoint and
the per-call log lines added in Initiative 6. The store is process-
local; this file tests the data shape, sort order and aggregation
rules in isolation.
"""

from __future__ import annotations

import time

from app.services.specialist_metrics import (
    SpecialistMetrics,
    get_specialist_metrics,
)


def test_singleton_returns_same_instance():
    a = get_specialist_metrics()
    b = get_specialist_metrics()
    assert a is b


def test_record_increments_call_counters_and_token_sums():
    m = SpecialistMetrics()
    m.record(
        name="scout",
        model="claude-sonnet-4",
        input_tokens=100,
        output_tokens=40,
        elapsed_ms=1200,
        success=True,
        is_byok=False,
    )
    m.record(
        name="scout",
        model="claude-sonnet-4",
        input_tokens=80,
        output_tokens=30,
        elapsed_ms=900,
        success=True,
        is_byok=False,
    )
    snap = m.snapshot()
    [scout] = snap["specialists"]
    assert scout["name"] == "scout"
    assert scout["calls"] == 2
    assert scout["successes"] == 2
    assert scout["failures"] == 0
    assert scout["input_tokens"] == 180
    assert scout["output_tokens"] == 70
    assert scout["total_tokens"] == 250
    assert scout["total_elapsed_ms"] == 2100
    assert scout["avg_elapsed_ms"] == 1050


def test_failed_calls_bump_failures_and_keep_last_error():
    m = SpecialistMetrics()
    m.record(
        name="analyst",
        model="claude-sonnet-4",
        input_tokens=0,
        output_tokens=0,
        elapsed_ms=300,
        success=False,
        is_byok=False,
        error="connection reset",
    )
    snap = m.snapshot()
    [a] = snap["specialists"]
    assert a["calls"] == 1
    assert a["successes"] == 0
    assert a["failures"] == 1
    assert a["last_error"] == "connection reset"


def test_byok_calls_are_counted_separately():
    m = SpecialistMetrics()
    m.record(
        name="scout",
        model="gpt-4o",
        input_tokens=10,
        output_tokens=5,
        elapsed_ms=200,
        success=True,
        is_byok=True,
    )
    m.record(
        name="scout",
        model="claude-sonnet-4",
        input_tokens=10,
        output_tokens=5,
        elapsed_ms=200,
        success=True,
        is_byok=False,
    )
    [scout] = m.snapshot()["specialists"]
    assert scout["calls"] == 2
    assert scout["byok_calls"] == 1
    # Each model used once; the order doesn't matter here but the dict
    # should account for both.
    assert scout["models_used"] == {"gpt-4o": 1, "claude-sonnet-4": 1}


def test_snapshot_is_sorted_by_calls_desc_then_name_asc():
    m = SpecialistMetrics()
    for _ in range(3):
        m.record(
            name="analyst", model="x", input_tokens=0, output_tokens=0,
            elapsed_ms=10, success=True, is_byok=False,
        )
    m.record(
        name="scout", model="x", input_tokens=0, output_tokens=0,
        elapsed_ms=10, success=True, is_byok=False,
    )
    m.record(
        name="matchmaker", model="x", input_tokens=0, output_tokens=0,
        elapsed_ms=10, success=True, is_byok=False,
    )
    names = [s["name"] for s in m.snapshot()["specialists"]]
    # analyst (3 calls) first; scout and matchmaker tied at 1 — sorted alpha.
    assert names == ["analyst", "matchmaker", "scout"]


def test_uptime_grows_over_time():
    m = SpecialistMetrics()
    snap1 = m.snapshot()
    time.sleep(0.05)
    snap2 = m.snapshot()
    assert snap2["uptime_seconds"] >= snap1["uptime_seconds"]


def test_reset_clears_counters_and_resets_started_at():
    m = SpecialistMetrics()
    m.record(
        name="scout", model="x", input_tokens=10, output_tokens=10,
        elapsed_ms=10, success=True, is_byok=False,
    )
    assert m.snapshot()["specialists"]
    started_before = m.snapshot()["process_started_at"]
    time.sleep(0.01)
    m.reset()
    snap = m.snapshot()
    assert snap["specialists"] == []
    assert snap["process_started_at"] > started_before


def test_negative_inputs_are_clamped_to_zero():
    # Defensive: a buggy provider returning -1 should not poison the
    # totals to "less than nothing".
    m = SpecialistMetrics()
    m.record(
        name="scout", model="x", input_tokens=-50, output_tokens=-1,
        elapsed_ms=-10, success=True, is_byok=False,
    )
    [scout] = m.snapshot()["specialists"]
    assert scout["input_tokens"] == 0
    assert scout["output_tokens"] == 0
    assert scout["total_elapsed_ms"] == 0
