"""
Test script for void analysis agent chaining.

This script tests that void analysis receives real demographics and tenant data
from the Census API and Google Places before generating its analysis.

Usage:
    cd backend
    python -m scripts.test_void_chaining
"""

import asyncio
import sys
from pathlib import Path

# Add backend to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.census import get_demographics_structured
from app.services.places import get_tenants_structured
from app.agents.void_analysis import generate_void_report


async def test_void_analysis_with_real_data():
    """Test the full agent chaining flow with real API data."""
    address = "123 Main St, Weston, CT 06883"

    print("=" * 60)
    print("VOID ANALYSIS AGENT CHAINING TEST")
    print("=" * 60)
    print(f"\nTest Address: {address}\n")

    # Step 1: Fetch demographics
    print("1. Fetching demographics from Census API...")
    demographics = await get_demographics_structured(address)

    if demographics:
        print("   Demographics data received:")
        for key, value in demographics.items():
            if isinstance(value, (int, float)):
                print(f"     - {key}: {value:,}" if isinstance(value, int) else f"     - {key}: {value}")
            else:
                print(f"     - {key}: {value}")
    else:
        print("   WARNING: No demographics data returned (geocoding may have failed)")

    # Step 2: Fetch tenants
    print("\n2. Fetching tenants from Google Places API...")
    tenants = await get_tenants_structured(address)

    if tenants:
        print(f"   Found {len(tenants)} businesses nearby:")
        # Group by category for summary
        categories = {}
        for t in tenants:
            cat = t.get("category", "Other")
            categories[cat] = categories.get(cat, 0) + 1
        for cat, count in sorted(categories.items(), key=lambda x: -x[1])[:10]:
            print(f"     - {cat}: {count}")
        if len(categories) > 10:
            print(f"     ... and {len(categories) - 10} more categories")
    else:
        print("   WARNING: No tenant data returned (Places API may need configuration)")

    # Step 3: Run void analysis with the data
    print("\n3. Running void analysis with chained data...")
    print("   (This calls Claude to analyze the data)")

    report = await generate_void_report(
        property_address=address,
        existing_tenants=tenants,
        demographics=demographics,
    )

    print("\n" + "=" * 60)
    print("VOID ANALYSIS REPORT")
    print("=" * 60)
    print(report)

    # Verification
    print("\n" + "=" * 60)
    print("VERIFICATION")
    print("=" * 60)

    checks = []

    # Check if demographics were used
    if demographics and demographics.get("population"):
        pop = demographics["population"]
        if str(pop) in report or f"{pop:,}" in report:
            checks.append(("Demographics referenced in report", True))
        else:
            checks.append(("Demographics referenced in report", False))
    else:
        checks.append(("Demographics data fetched", False))

    # Check if tenant categories were used
    if tenants:
        checks.append(("Tenant data fetched", True))
        # Check if any category names appear in report
        found_category = any(t.get("category", "") in report for t in tenants[:20])
        checks.append(("Tenant categories mentioned", found_category))
    else:
        checks.append(("Tenant data fetched", False))

    # Check report has content
    checks.append(("Report generated successfully", len(report) > 100))

    print()
    all_passed = True
    for check_name, passed in checks:
        status = "PASS" if passed else "FAIL"
        symbol = "✓" if passed else "✗"
        print(f"  {symbol} {check_name}: {status}")
        if not passed:
            all_passed = False

    print()
    if all_passed:
        print("All checks passed! Agent chaining is working correctly.")
    else:
        print("Some checks failed. Review the output above for details.")

    return all_passed


if __name__ == "__main__":
    success = asyncio.run(test_void_analysis_with_real_data())
    sys.exit(0 if success else 1)
