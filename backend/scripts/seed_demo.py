#!/usr/bin/env python3
"""
Seed script to create a demo user with sample data for the broker demo flow.

Usage:
    python -m scripts.seed_demo           # Create demo user + seed data
    python -m scripts.seed_demo --reset   # Delete and recreate from scratch

Creates:
    - User: demo@spacegoose.test / spacegoosedemo
    - A clean chat session ready for the demo
    - One sample CoStar CSV import
    - One sample SiteUSA CSV import
"""

import asyncio
import json
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import delete, select

from app.core.database import async_session_factory
from app.core.security import hash_password
from app.db.models.user import User
from app.db.models.credential import OnboardingProgress
from app.db.models.chat import ChatSession
from app.db.models.import_job import ImportJob

DEMO_EMAIL = "demo@spacegoose.test"
DEMO_PASSWORD = "spacegoosedemo"
DEMO_FIRST = "Demo"
DEMO_LAST = "Broker"

# Sample CoStar lease comp data
SAMPLE_COSTAR_PAYLOAD = json.dumps({
    "property_name": "Westport Village Center",
    "address": "1460 Post Rd E, Westport, CT 06880",
    "total_sf": 125000,
    "year_built": 1998,
    "tenants": [
        {"name": "Whole Foods Market", "suite": "100", "square_feet": 40000, "category": "Grocery", "is_anchor": True},
        {"name": "Athleta", "suite": "110", "square_feet": 4200, "rent_psf": 45.0, "category": "Apparel"},
        {"name": "Starbucks", "suite": "120", "square_feet": 1800, "rent_psf": 55.0, "category": "Coffee/Quick Service"},
        {"name": "Chase Bank", "suite": "130", "square_feet": 3500, "rent_psf": 40.0, "category": "Financial Services"},
        {"name": "Vacant", "suite": "140", "square_feet": 4200, "rent_psf": 48.0, "category": "Endcap w/ Drive-Thru"},
        {"name": "Vacant", "suite": "150", "square_feet": 2200, "rent_psf": 52.0, "category": "Inline"},
    ],
})

# Sample SiteUSA traffic data
SAMPLE_SITEUSA_PAYLOAD = json.dumps({
    "address": "1460 Post Rd E, Westport, CT 06880",
    "vpd_average": 28500,
    "vpd_peak": 34200,
    "population_1mi": 8420,
    "population_3mi": 42100,
    "population_5mi": 89300,
    "median_hhi_3mi": 185000,
    "avg_age_3mi": 42.3,
})


async def seed_demo(reset: bool = False) -> None:
    async with async_session_factory() as db:
        # Check for existing user
        result = await db.execute(select(User).where(User.email == DEMO_EMAIL))
        existing = result.scalar_one_or_none()

        if existing and reset:
            print(f"Resetting demo user {DEMO_EMAIL}...")
            # Delete related data
            await db.execute(delete(ImportJob).where(ImportJob.user_id == existing.id))
            await db.execute(delete(ChatSession).where(ChatSession.user_id == existing.id))
            await db.execute(delete(OnboardingProgress).where(OnboardingProgress.user_id == existing.id))
            await db.execute(delete(User).where(User.id == existing.id))
            await db.commit()
            existing = None
            print("  Deleted existing demo data.")

        if existing:
            user = existing
            user.password_hash = hash_password(DEMO_PASSWORD)
            print(f"Demo user already exists (id: {user.id}), updated password.")
        else:
            user = User(
                email=DEMO_EMAIL,
                password_hash=hash_password(DEMO_PASSWORD),
                first_name=DEMO_FIRST,
                last_name=DEMO_LAST,
                email_verified=True,
                is_active=True,
                has_completed_onboarding=True,
                tier="individual",
            )
            db.add(user)
            await db.flush()

            onboarding = OnboardingProgress(
                user_id=user.id,
                current_step=999,
                completed_steps='["welcome","import","connect","ai_key","complete"]',
                completed_at=datetime.now(timezone.utc),
            )
            db.add(onboarding)
            print(f"Created demo user: {DEMO_EMAIL} (id: {user.id})")

        # Seed CoStar import
        result = await db.execute(
            select(ImportJob).where(
                ImportJob.user_id == user.id,
                ImportJob.source == "costar",
            )
        )
        if not result.scalar_one_or_none():
            costar_import = ImportJob(
                user_id=user.id,
                source="costar",
                status="ready",
                original_filename="westport_village_center_leases.csv",
                parsed_payload_json=SAMPLE_COSTAR_PAYLOAD,
                record_count=6,
            )
            db.add(costar_import)
            print("  Seeded CoStar import (Westport Village Center)")

        # Seed SiteUSA import
        result = await db.execute(
            select(ImportJob).where(
                ImportJob.user_id == user.id,
                ImportJob.source == "siteusa",
            )
        )
        if not result.scalar_one_or_none():
            siteusa_import = ImportJob(
                user_id=user.id,
                source="siteusa",
                status="ready",
                original_filename="westport_post_rd_traffic.csv",
                parsed_payload_json=SAMPLE_SITEUSA_PAYLOAD,
                record_count=1,
            )
            db.add(siteusa_import)
            print("  Seeded SiteUSA import (traffic data)")

        # Create a fresh chat session
        result = await db.execute(
            select(ChatSession).where(ChatSession.user_id == user.id)
        )
        if not result.scalars().first():
            session = ChatSession(
                user_id=user.id,
                title="New Analysis",
            )
            db.add(session)
            print("  Created fresh chat session")

        await db.commit()

        print()
        print("=" * 50)
        print("Demo account ready!")
        print("=" * 50)
        print(f"  Email:    {DEMO_EMAIL}")
        print(f"  Password: {DEMO_PASSWORD}")
        print()
        print("Demo script:")
        print('  1. Log in as demo@spacegoose.test')
        print('  2. Upload a leasing flyer PDF (or use seeded data)')
        print('  3. Ask: "Find me 5 strong tenant candidates for the 4,200 SF endcap with drive-thru"')
        print('  4. Watch Scout -> Analyst -> Matchmaker specialists run')
        print('  5. Ask: "Draft outreach to all 5 candidates"')
        print('  6. Review and send drafts')


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Seed demo user and data")
    parser.add_argument("--reset", action="store_true", help="Delete and recreate demo data")
    args = parser.parse_args()

    asyncio.run(seed_demo(reset=args.reset))


if __name__ == "__main__":
    main()
