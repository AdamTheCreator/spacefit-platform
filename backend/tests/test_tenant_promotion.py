"""Unit tests for void → Contacts promotion.

The pure pieces (``extract_promotable_tenants`` + the capture sink) are tested
directly. ``promote_tenants_to_contacts`` is exercised against a stubbed
``AsyncSession`` (the established convention — see ``test_outreach_replies.py``)
so the de-dupe + field-mapping logic is pinned without a real DB. The live chat
``tenant_candidates`` emission needs a running WS turn and can't be driven here.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from app.services.tenant_promotion import (
    MAX_PROMOTABLE_TENANTS,
    _tenant_capture_sink,
    begin_tenant_capture,
    extract_promotable_tenants,
    promote_tenants_to_contacts,
    record_promotable_tenants,
)


def _void(categories: list[dict]) -> dict:
    return {"categories": categories}


class TestExtractPromotableTenants:
    def test_empty_and_garbage_inputs(self):
        assert extract_promotable_tenants(None) == []
        assert extract_promotable_tenants({}) == []
        assert extract_promotable_tenants({"categories": "nope"}) == []
        assert extract_promotable_tenants({"categories": []}) == []

    def test_basic_flatten_and_fields(self):
        out = extract_promotable_tenants(
            _void(
                [
                    {
                        "category_name": "Fast Casual Mediterranean",
                        "parent_category": "Fast Casual Dining",
                        "is_void": True,
                        "match_score": 89,
                        "priority": "High",
                        "estimated_sf_need": 2200,
                        "rationale": "Underserved given daytime employment.",
                        "suggested_tenants": ["Cava", "Naf Naf Grill"],
                    }
                ]
            ),
            source_address="100 Main St, Reno, NV",
        )
        assert [t["name"] for t in out] == ["Cava", "Naf Naf Grill"]
        first = out[0]
        assert first["sector"] == "Fast Casual Dining"
        assert first["category"] == "Fast Casual Mediterranean"
        assert first["estimated_sf"] == 2200
        assert first["priority"] == "high"  # normalized lower
        assert first["match_score"] == 89
        assert first["source_address"] == "100 Main St, Reno, NV"
        assert "Underserved" in first["rationale"]

    def test_skips_non_void_categories(self):
        out = extract_promotable_tenants(
            _void(
                [
                    {"category_name": "Grocery", "is_void": False,
                     "suggested_tenants": ["Aldi"]},
                    {"category_name": "Coffee", "is_void": True,
                     "suggested_tenants": ["Dutch Bros"]},
                ]
            )
        )
        assert [t["name"] for t in out] == ["Dutch Bros"]

    def test_dedupe_case_insensitive(self):
        out = extract_promotable_tenants(
            _void(
                [
                    {"category_name": "A", "is_void": True, "match_score": 90,
                     "suggested_tenants": ["Cava", "cava", "CAVA"]},
                    {"category_name": "B", "is_void": True, "match_score": 80,
                     "suggested_tenants": ["Cava"]},
                ]
            )
        )
        assert [t["name"] for t in out] == ["Cava"]

    def test_ranks_by_match_score_desc(self):
        out = extract_promotable_tenants(
            _void(
                [
                    {"category_name": "Low", "is_void": True, "match_score": 40,
                     "suggested_tenants": ["LowBrand"]},
                    {"category_name": "High", "is_void": True, "match_score": 95,
                     "suggested_tenants": ["HighBrand"]},
                ]
            )
        )
        assert [t["name"] for t in out] == ["HighBrand", "LowBrand"]

    def test_category_fallback_when_no_brands(self):
        out = extract_promotable_tenants(
            _void(
                [
                    {
                        "category_name": "Urgent Care",
                        "parent_category": "Medical/Healthcare",
                        "is_void": True,
                        "suggested_tenants": [],
                    }
                ]
            )
        )
        assert [t["name"] for t in out] == ["Urgent Care"]
        assert out[0]["sector"] == "Medical/Healthcare"

    def test_caps_at_max(self):
        cats = [
            {
                "category_name": f"C{i}",
                "is_void": True,
                "match_score": i,
                "suggested_tenants": [f"Brand{i}"],
            }
            for i in range(MAX_PROMOTABLE_TENANTS + 10)
        ]
        out = extract_promotable_tenants(_void(cats))
        assert len(out) == MAX_PROMOTABLE_TENANTS


class TestCaptureSink:
    def test_record_without_begin_is_noop(self):
        _tenant_capture_sink.set(None)  # ensure capture is off
        # Must not raise and must not store anything.
        record_promotable_tenants([{"name": "Cava"}])
        assert _tenant_capture_sink.get() is None

    def test_begin_then_record_collects(self):
        sink = begin_tenant_capture()
        record_promotable_tenants([{"name": "Cava"}])
        record_promotable_tenants([{"name": "Dutch Bros"}])
        assert [t["name"] for t in sink] == ["Cava", "Dutch Bros"]

    def test_begin_overwrites_previous_turn(self):
        first = begin_tenant_capture()
        record_promotable_tenants([{"name": "Cava"}])
        second = begin_tenant_capture()
        assert second is not first
        assert second == []
        record_promotable_tenants([{"name": "Sweetgreen"}])
        assert [t["name"] for t in second] == ["Sweetgreen"]
        assert [t["name"] for t in first] == ["Cava"]  # old list untouched


def _stub_db(existing_lower_names: list[str]) -> MagicMock:
    db = MagicMock()
    result = MagicMock()
    result.scalars.return_value.all.return_value = existing_lower_names
    db.execute = AsyncMock(return_value=result)
    db.add = MagicMock()
    db.flush = AsyncMock()
    db.commit = AsyncMock()
    return db


class TestPromoteTenantsToContacts:
    async def test_creates_and_dedupes(self):
        db = _stub_db(["chipotle"])  # user already has Chipotle
        tenants = [
            {"name": "Chipotle", "sector": "Fast Casual"},  # dup -> skip
            {"name": "Cava", "sector": "Fast Casual", "estimated_sf": 2200,
             "category": "Mediterranean", "match_score": 88, "priority": "high",
             "rationale": "Strong fit", "source_address": "100 Main St"},
            {"name": "cava", "sector": "Fast Casual"},  # in-batch dup -> skip
        ]
        result = await promote_tenants_to_contacts(db, "u1", tenants)

        assert result["created"] == 1
        assert result["skipped"] == 2
        assert [c["name"] for c in result["companies"]] == ["Cava"]
        db.commit.assert_awaited_once()

        # Inspect the Company that was added.
        assert db.add.call_count == 1
        company = db.add.call_args.args[0]
        assert company.name == "Cava"
        assert company.user_id == "u1"
        assert company.is_expanding is True
        assert company.sf_min == 2200 and company.sf_max == 2200
        assert company.criteria["source"] == "void_analysis"
        assert company.criteria["source_property"] == "100 Main St"
        assert company.criteria["void_category"] == "Mediterranean"
        assert company.notes == "Strong fit"

    async def test_empty_input_creates_nothing(self):
        db = _stub_db([])
        result = await promote_tenants_to_contacts(db, "u1", [])
        assert result == {"created": 0, "skipped": 0, "companies": []}
        db.add.assert_not_called()
        # Nothing created -> no flush needed, but commit still closes the unit.
        db.commit.assert_awaited_once()

    async def test_source_address_fallback_from_context(self):
        db = _stub_db([])
        tenants = [{"name": "Sweetgreen"}]  # no per-tenant source_address
        await promote_tenants_to_contacts(
            db, "u1", tenants, source={"address": "5th & Main, Reno NV"}
        )
        company = db.add.call_args.args[0]
        assert company.criteria["source_property"] == "5th & Main, Reno NV"
