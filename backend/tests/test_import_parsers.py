"""Tests for CoStar CSV, Placer PDF, and SiteUSA CSV import parsers."""

from pathlib import Path

import pytest

from app.services.imports.costar_csv import parse_costar_csv, _detect_export_type
from app.services.imports.siteusa_csv import parse_siteusa_csv

FIXTURES = Path(__file__).parent / "fixtures" / "imports"


class TestCostarCSV:
    def test_parse_leasing_export(self):
        data = (FIXTURES / "costar_leasing.csv").read_bytes()
        results = parse_costar_csv(data)

        assert len(results) == 2  # two properties

        # First property
        westport = next(p for p in results if "1842" in p.address)
        assert westport.property_name == "Westport Plaza"
        assert westport.city == "Westport"
        assert westport.state == "CT"
        assert len(westport.tenants) == 3
        assert westport.source == "costar"

        starbucks = next(t for t in westport.tenants if t.name == "Starbucks")
        assert starbucks.suite == "101"
        assert starbucks.square_feet == 1800
        assert starbucks.rent_psf == 45.0
        assert starbucks.lease_start is not None
        assert starbucks.source == "costar"

        # Second property
        fairfield = next(p for p in results if "2100" in p.address)
        assert len(fairfield.tenants) == 2

    def test_parse_roster_export(self):
        data = (FIXTURES / "costar_roster.csv").read_bytes()
        results = parse_costar_csv(data)

        assert len(results) == 1
        prop = results[0]
        assert len(prop.tenants) == 3

        tj = next(t for t in prop.tenants if "Trader" in t.name)
        assert tj.square_feet == 14000

    def test_detect_leasing_type(self):
        headers = ["Property Name", "Tenant Name", "Lease Start", "Lease End", "Rent ($/SF)"]
        assert _detect_export_type(headers) == "leasing"

    def test_detect_roster_type(self):
        headers = ["Tenant", "Suite/Unit", "Occupied SF", "Property Address"]
        assert _detect_export_type(headers) == "roster"

    def test_empty_csv_raises(self):
        with pytest.raises(ValueError, match="Empty CSV"):
            parse_costar_csv(b"")

    def test_unmapped_headers_raises(self):
        with pytest.raises(ValueError, match="Could not map"):
            parse_costar_csv(b"foo,bar,baz\n1,2,3\n")

    def test_bom_handling(self):
        """UTF-8 BOM should not break parsing."""
        data = b"\xef\xbb\xbf" + (FIXTURES / "costar_leasing.csv").read_bytes()
        results = parse_costar_csv(data)
        assert len(results) == 2

    def test_blank_rows_skipped(self):
        data = (FIXTURES / "costar_leasing.csv").read_bytes()
        lines = data.decode().split("\n")
        # Insert blank rows
        lines.insert(2, ",,,,,,,,,,,")
        lines.insert(4, "")
        modified = "\n".join(lines).encode()
        results = parse_costar_csv(modified)
        assert len(results) == 2


class TestSiteUSACSV:
    def test_parse_traffic_export(self):
        data = (FIXTURES / "siteusa_traffic.csv").read_bytes()
        results = parse_siteusa_csv(data)

        assert len(results) == 2

        westport = next(r for r in results if "1842" in r.address)
        assert westport.road_name == "Boston Post Rd"
        assert westport.vpd == 28500
        assert westport.population_1mi == 8200
        assert westport.median_hhi_3mi == 145000.0
        assert westport.source == "siteusa"

    def test_empty_csv_raises(self):
        with pytest.raises(ValueError, match="Empty CSV"):
            parse_siteusa_csv(b"")

    def test_no_address_column_raises(self):
        with pytest.raises(ValueError, match="address column"):
            parse_siteusa_csv(b"VPD,Road Name\n28500,Main St\n")

    def test_unmapped_headers_raises(self):
        with pytest.raises(ValueError, match="Could not map"):
            parse_siteusa_csv(b"foo,bar\n1,2\n")


# Placer PDF tests are skipped in CI — they require Claude Vision API access.
# See test_placer_pdf_parser_integration.py for manual E2E tests.
class TestPlacerPDFSkipped:
    @pytest.mark.skip(reason="Requires Claude Vision API — run manually")
    def test_parse_placer_pdf(self):
        pass
