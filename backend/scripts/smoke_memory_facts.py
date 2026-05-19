"""End-to-end smoke test for the personal facts memory layer.

What this script exercises (no live LLM required):

  1. Health check → confirm uvicorn answers.
  2. Login as the seeded ``pro@spacegoose.io`` user.
  3. Seed three ``pending`` facts directly via the DB so the LLM isn't needed.
  4. ``GET /users/me/memory/facts?status_filter=pending`` returns all three.
  5. ``POST /users/me/memory/facts/{id}/approve`` flips status + stamps approved_at.
  6. ``GET /users/me/memory/facts?status_filter=approved`` returns the approved one.
  7. ``POST /users/me/memory/facts/{id}/reject`` flips a different fact.
  8. ``DELETE /users/me/memory/facts/{id}`` archives the approved fact.
  9. Final list (no filter) excludes archived.
 10. Cross-user ownership: a second user cannot approve another user's fact (expect 404).

The script boots its own uvicorn on a non-default port so it doesn't
collide with a running dev server. Exit code is 0 on success, non-zero
on any failed assertion or HTTP error.

Usage:
    backend/.venv/bin/python -m scripts.smoke_memory_facts

Optional env:
    SMOKE_PORT     uvicorn port (default 8765)
    SMOKE_BASE_URL skip uvicorn boot and hit this URL instead
                   (useful when iterating against a running dev server)
"""

from __future__ import annotations

import asyncio
import logging
import os
import signal
import subprocess
import sys
import time
import uuid
from typing import Any

import httpx

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import async_session_factory  # noqa: E402
from app.db.models.user import User  # noqa: E402
from app.db.models.user_fact import UserFact  # noqa: E402
from sqlalchemy import delete, select  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("smoke")


PRO_EMAIL = "pro@spacegoose.io"
PRO_PASSWORD = "protest1234"
BYOK_EMAIL = "byok@spacegoose.io"
BYOK_PASSWORD = "byoktest1234"


def _assert(cond: bool, msg: str) -> None:
    if not cond:
        logger.error("FAIL: %s", msg)
        raise SystemExit(2)
    logger.info("  ok: %s", msg)


async def _seed_pending_facts(user_id: str) -> list[str]:
    """Insert three pending facts for the user, return their IDs.

    Wipes any existing user_facts for the user first so the run is
    reproducible.
    """
    async with async_session_factory() as db:
        await db.execute(delete(UserFact).where(UserFact.user_id == user_id))
        ids = [str(uuid.uuid4()) for _ in range(3)]
        for fid, text, category in zip(
            ids,
            [
                "prefers Texas multifamily, $5-15M deals",
                "works the Charlotte trade area",
                "owns a niche kombucha startup",
            ],
            ["deal_prefs", "geography", "personal"],
        ):
            fact = UserFact(
                user_id=user_id,
                text=text,
                category=category,
                status="pending",
                confidence=0.8,
            )
            fact.id = fid
            db.add(fact)
        await db.commit()
    return ids


async def _resolve_user_id(email: str) -> str:
    async with async_session_factory() as db:
        row = (
            await db.execute(select(User).where(User.email == email))
        ).scalar_one_or_none()
        if row is None:
            raise SystemExit(f"seed user {email!r} not present — run scripts.seed_test_users first")
        return row.id


async def _seed_users_if_needed() -> None:
    async with async_session_factory() as db:
        for email in (PRO_EMAIL, BYOK_EMAIL):
            row = (
                await db.execute(select(User).where(User.email == email))
            ).scalar_one_or_none()
            if row is None:
                # Defer to the existing idempotent seed.
                logger.info("seeding test users via scripts.seed_test_users…")
                from scripts.seed_test_users import main as seed_main

                await seed_main()
                return


def _boot_uvicorn(port: int) -> subprocess.Popen[bytes]:
    backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    cmd = [
        sys.executable,
        "-m",
        "uvicorn",
        "app.main:app",
        "--port",
        str(port),
        "--log-level",
        "info",
    ]
    logger.info("booting uvicorn: %s", " ".join(cmd))
    # IMPORTANT: do NOT capture stdout with PIPE — SQLAlchemy echo + uvicorn
    # access logs will overflow the pipe buffer (~64KB on macOS) and the
    # uvicorn worker will block on a future write, which looks like a hang
    # from the client side. Send output to DEVNULL when we don't need it.
    proc = subprocess.Popen(
        cmd,
        cwd=backend_dir,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        env={**os.environ, "PYTHONUNBUFFERED": "1"},
    )
    # Wait for it to come up.
    deadline = time.monotonic() + 25
    while time.monotonic() < deadline:
        time.sleep(0.3)
        try:
            r = httpx.get(f"http://127.0.0.1:{port}/health", timeout=1.0)
            if r.status_code == 200:
                logger.info("uvicorn up on :%d", port)
                return proc
        except httpx.HTTPError:
            pass
        if proc.poll() is not None:
            raise SystemExit(
                f"uvicorn exited before /health responded "
                f"(rc={proc.returncode}). Re-run with `--log-level info` "
                f"manually to see the stack trace."
            )
    proc.terminate()
    raise SystemExit("uvicorn did not become healthy within 25s")


async def _run_smoke(base_url: str) -> None:
    await _seed_users_if_needed()
    pro_user_id = await _resolve_user_id(PRO_EMAIL)
    byok_user_id = await _resolve_user_id(BYOK_EMAIL)

    fact_ids = await _seed_pending_facts(pro_user_id)
    # Seed one fact for the byok user too, so the cross-user check has
    # something to target without affecting the pro user's list.
    await _seed_pending_facts(byok_user_id)

    limits = httpx.Limits(max_keepalive_connections=0, max_connections=10)
    async with httpx.AsyncClient(
        base_url=base_url, timeout=30.0, limits=limits
    ) as client:
        # 1. Health.
        r = await client.get("/health")
        _assert(r.status_code == 200, f"GET /health → {r.status_code}")

        # 2. Login.
        r = await client.post(
            "/api/v1/auth/login",
            json={"email": PRO_EMAIL, "password": PRO_PASSWORD},
        )
        _assert(
            r.status_code == 200,
            f"POST /auth/login → {r.status_code} {r.text[:120]}",
        )
        pro_token = r.json()["access_token"]
        pro_hdrs = {"Authorization": f"Bearer {pro_token}"}

        r = await client.post(
            "/api/v1/auth/login",
            json={"email": BYOK_EMAIL, "password": BYOK_PASSWORD},
        )
        _assert(r.status_code == 200, "byok login")
        byok_token = r.json()["access_token"]
        byok_hdrs = {"Authorization": f"Bearer {byok_token}"}

        # 3. List pending — expect 3.
        r = await client.get(
            "/api/v1/users/me/memory/facts",
            params={"status_filter": "pending"},
            headers=pro_hdrs,
        )
        _assert(r.status_code == 200, f"GET facts?pending → {r.status_code}")
        rows: list[dict[str, Any]] = r.json()
        _assert(len(rows) == 3, f"pending count is 3 (got {len(rows)})")
        seen_ids = {row["id"] for row in rows}
        _assert(set(fact_ids).issubset(seen_ids), "seeded fact ids present")

        # 4. Approve fact 0.
        f0 = fact_ids[0]
        r = await client.post(
            f"/api/v1/users/me/memory/facts/{f0}/approve",
            headers=pro_hdrs,
        )
        _assert(r.status_code == 200, f"approve → {r.status_code}")
        body = r.json()
        _assert(body["status"] == "approved", "status flipped to approved")
        _assert(body["approved_at"] is not None, "approved_at stamped")

        # 5. List approved — expect 1.
        r = await client.get(
            "/api/v1/users/me/memory/facts",
            params={"status_filter": "approved"},
            headers=pro_hdrs,
        )
        approved = r.json()
        _assert(len(approved) == 1, f"approved count is 1 (got {len(approved)})")
        _assert(approved[0]["id"] == f0, "right id approved")

        # 6. Reject fact 1.
        f1 = fact_ids[1]
        r = await client.post(
            f"/api/v1/users/me/memory/facts/{f1}/reject",
            headers=pro_hdrs,
        )
        _assert(r.status_code == 200, "reject → 200")
        _assert(r.json()["status"] == "rejected", "rejected status set")

        # 7. Archive the approved one (DELETE → 204).
        r = await client.delete(
            f"/api/v1/users/me/memory/facts/{f0}",
            headers=pro_hdrs,
        )
        _assert(r.status_code == 204, f"archive → {r.status_code}")

        # 8. Final list (no filter) excludes archived.
        r = await client.get(
            "/api/v1/users/me/memory/facts",
            headers=pro_hdrs,
        )
        remaining = r.json()
        _assert(
            f0 not in {row["id"] for row in remaining},
            "archived fact hidden from default list",
        )
        # Should include fact 1 (rejected — still shown unless filter says otherwise)
        # and fact 2 (still pending).
        statuses = {row["id"]: row["status"] for row in remaining}
        _assert(statuses.get(f1) == "rejected", "fact 1 still listed as rejected")
        _assert(statuses.get(fact_ids[2]) == "pending", "fact 2 still pending")

        # 9. Cross-user ownership — byok user tries to approve a pro user's fact.
        r = await client.post(
            f"/api/v1/users/me/memory/facts/{fact_ids[2]}/approve",
            headers=byok_hdrs,
        )
        _assert(r.status_code == 404, f"cross-user approve → {r.status_code} (expected 404)")

        # 10. Memory endpoint stays responsive even though structured memory is empty.
        r = await client.get("/api/v1/users/me/memory", headers=pro_hdrs)
        _assert(
            r.status_code == 200,
            f"GET /users/me/memory → {r.status_code}",
        )

        # 11. Stats endpoint.
        r = await client.get("/api/v1/users/me/memory/stats", headers=pro_hdrs)
        _assert(r.status_code == 200, "GET /memory/stats → 200")
        stats = r.json()
        _assert("total_analyses" in stats, "stats payload shape ok")

    logger.info("\nALL SMOKE CHECKS PASSED")


async def main() -> None:
    port = int(os.environ.get("SMOKE_PORT", "8765"))
    override_base = os.environ.get("SMOKE_BASE_URL")

    if override_base:
        logger.info("using existing server at %s", override_base)
        await _run_smoke(override_base)
        return

    proc = _boot_uvicorn(port)
    try:
        await _run_smoke(f"http://127.0.0.1:{port}")
    finally:
        logger.info("shutting down uvicorn (pid=%d)", proc.pid)
        proc.send_signal(signal.SIGTERM)
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


if __name__ == "__main__":
    asyncio.run(main())
