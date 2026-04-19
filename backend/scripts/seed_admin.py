#!/usr/bin/env python3
"""
Seed script to create an admin user with pre-configured connectors for testing.

Usage:
    python -m scripts.seed_admin                    # Create/update admin account
    python -m scripts.seed_admin --verify           # Verify admin can log in
    python -m scripts.seed_admin --verify-connectors # Verify connector credentials (browser test)

Required environment variables:
    ADMIN_PASSWORD          - Password for the admin account

Optional connector credentials (set the ones you have):
    SITEUSA_USERNAME        - SitesUSA username
    SITEUSA_PASSWORD        - SitesUSA password
    PLACER_USERNAME         - Placer username
    PLACER_PASSWORD         - Placer password
    COSTAR_USERNAME         - CoStar username
    COSTAR_PASSWORD         - CoStar password
"""

import argparse
import asyncio
import os
import sys
from datetime import datetime, timezone

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select

from app.core.database import async_session_factory
from app.core.security import (
    hash_password,
    encrypt_credential,
    decrypt_credential,
    verify_password,
    create_access_token,
)
from app.db.models.user import User
from app.db.models.credential import SiteCredential, OnboardingProgress


ADMIN_EMAIL = "admin@perigee.com"
ADMIN_FIRST_NAME = "Admin"
ADMIN_LAST_NAME = "Tester"

# Connector configurations
CONNECTORS = [
    {
        "name": "siteusa",
        "url": "https://www.sitesusa.com",
        "username_env": "SITEUSA_USERNAME",
        "password_env": "SITEUSA_PASSWORD",
    },
    {
        "name": "placer",
        "url": "https://www.placer.ai",
        "username_env": "PLACER_USERNAME",
        "password_env": "PLACER_PASSWORD",
    },
    {
        "name": "costar",
        "url": "https://www.costar.com",
        "username_env": "COSTAR_USERNAME",
        "password_env": "COSTAR_PASSWORD",
    },
]


async def seed_admin() -> str | None:
    """Create or update admin user with pre-configured connectors.

    Returns the user ID if successful.
    """
    admin_password = os.environ.get("ADMIN_PASSWORD")
    if not admin_password:
        print("ERROR: ADMIN_PASSWORD environment variable is required")
        print("Set it with: export ADMIN_PASSWORD='your-secure-password'")
        sys.exit(1)

    async with async_session_factory() as db:
        # Check if admin user already exists
        result = await db.execute(
            select(User).where(User.email == ADMIN_EMAIL)
        )
        existing_user = result.scalar_one_or_none()

        if existing_user:
            print(f"Admin user {ADMIN_EMAIL} already exists (id: {existing_user.id})")
            user = existing_user
            # Update password in case it changed
            user.password_hash = hash_password(admin_password)
            user.is_superuser = True
            print("  - Updated password and ensured superuser status")
        else:
            # Create new admin user
            user = User(
                email=ADMIN_EMAIL,
                password_hash=hash_password(admin_password),
                first_name=ADMIN_FIRST_NAME,
                last_name=ADMIN_LAST_NAME,
                email_verified=True,
                is_active=True,
                is_superuser=True,
            )
            db.add(user)
            await db.flush()  # Get the user ID

            # Create onboarding progress (mark as complete)
            onboarding = OnboardingProgress(
                user_id=user.id,
                current_step=999,
                completed_steps='["welcome", "profile", "connectors"]',
                completed_at=datetime.now(timezone.utc),
            )
            db.add(onboarding)

            print(f"Created admin user: {ADMIN_EMAIL} (id: {user.id})")

        # Set up connectors
        connectors_added = 0
        for connector in CONNECTORS:
            username = os.environ.get(connector["username_env"])
            password = os.environ.get(connector["password_env"])

            if not username or not password:
                print(f"  - Skipping {connector['name']}: credentials not provided")
                continue

            # Check if credential already exists for this user+site
            result = await db.execute(
                select(SiteCredential).where(
                    SiteCredential.user_id == user.id,
                    SiteCredential.site_name == connector["name"],
                )
            )
            existing_cred = result.scalar_one_or_none()

            if existing_cred:
                # Update existing credential
                existing_cred.username_encrypted = encrypt_credential(username)
                existing_cred.password_encrypted = encrypt_credential(password)
                existing_cred.is_verified = True  # Mark as verified for testing
                existing_cred.session_status = "unknown"
                print(f"  - Updated {connector['name']} credentials")
            else:
                # Create new credential
                credential = SiteCredential(
                    user_id=user.id,
                    site_name=connector["name"],
                    site_url=connector["url"],
                    username_encrypted=encrypt_credential(username),
                    password_encrypted=encrypt_credential(password),
                    is_verified=True,  # Mark as verified for testing
                    session_status="unknown",
                )
                db.add(credential)
                print(f"  - Added {connector['name']} credentials")

            connectors_added += 1

        await db.commit()

        print()
        print("=" * 50)
        print("Admin account ready!")
        print("=" * 50)
        print(f"  Email:    {ADMIN_EMAIL}")
        print(f"  Password: (as set in ADMIN_PASSWORD)")
        print(f"  Connectors configured: {connectors_added}")
        print()
        if connectors_added == 0:
            print("NOTE: No connectors were configured.")
            print("Set environment variables for the connectors you want:")
            print("  export SITEUSA_USERNAME='...' SITEUSA_PASSWORD='...'")
            print("  export PLACER_USERNAME='...' PLACER_PASSWORD='...'")
            print("  export COSTAR_USERNAME='...' COSTAR_PASSWORD='...'")

        return user.id


async def verify_admin_login():
    """Verify that the admin account can authenticate."""
    print("Verifying admin login...")
    print()

    admin_password = os.environ.get("ADMIN_PASSWORD")
    if not admin_password:
        print("ERROR: ADMIN_PASSWORD environment variable is required")
        sys.exit(1)

    async with async_session_factory() as db:
        # Find admin user
        result = await db.execute(
            select(User).where(User.email == ADMIN_EMAIL)
        )
        user = result.scalar_one_or_none()

        if not user:
            print(f"FAILED: Admin user {ADMIN_EMAIL} not found")
            print("Run 'python -m scripts.seed_admin' first to create the account")
            sys.exit(1)

        # Verify password
        if not user.password_hash:
            print("FAILED: Admin user has no password set")
            sys.exit(1)

        if not verify_password(admin_password, user.password_hash):
            print("FAILED: Password verification failed")
            print("The ADMIN_PASSWORD doesn't match what's stored in the database")
            sys.exit(1)

        # Generate access token
        token = create_access_token(user.id)

        print("SUCCESS: Admin login verified!")
        print()
        print(f"  User ID:     {user.id}")
        print(f"  Email:       {user.email}")
        print(f"  Superuser:   {user.is_superuser}")
        print(f"  Active:      {user.is_active}")
        print()
        print("Sample access token (for testing API calls):")
        print(f"  {token[:50]}...")
        print()
        print("Use in requests as:")
        print(f'  curl -H "Authorization: Bearer {token[:20]}..." ...')


async def verify_connectors():
    """Verify connector credentials. Browser automation has been removed."""
    print("Browser-based connector verification has been removed.")
    print("Data sources now use CSV/PDF imports (Phase 2).")
    sys.exit(0)


def main():
    parser = argparse.ArgumentParser(
        description="Seed and manage the admin test account"
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Verify admin can log in (generates test token)",
    )
    parser.add_argument(
        "--verify-connectors",
        action="store_true",
        help="Verify connector credentials via browser login",
    )

    args = parser.parse_args()

    if args.verify:
        asyncio.run(verify_admin_login())
    elif args.verify_connectors:
        asyncio.run(verify_connectors())
    else:
        asyncio.run(seed_admin())


if __name__ == "__main__":
    main()
