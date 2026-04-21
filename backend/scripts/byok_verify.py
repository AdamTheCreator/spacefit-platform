#!/usr/bin/env python3
"""
byok_verify.py — end-to-end BYOK verification helper.

What this checks
----------------
1. Reads your current /ai-config state (provider, is_key_valid, has_byok_key).
2. Reads /ai-config/usage to snapshot platform-side token counters.
3. Waits for you to send one chat message through the UI.
4. Re-reads the counters and asserts:
     - If BYOK is valid and active: platform token counters must NOT move
       (after the 2026-04-21 guardrail + record_token_usage patches).
     - If BYOK is inactive: platform token counters SHOULD move.
5. Prints a PASS / FAIL verdict.

What this does NOT check
------------------------
- Your own provider's dashboard (Anthropic console, OpenAI platform). You have
  to eyeball those yourself to confirm tokens *did* land on your key.
- Backend logs. Tail them separately:
    render logs --tail --service perigee-api | grep -E "byok=|Resolved LLM"

Usage
-----
Two env vars are required:

    export PERIGEE_API=https://perigee-api.onrender.com
    # or locally:    PERIGEE_API=http://localhost:8000

    export PERIGEE_TOKEN=$(...)   # JWT from devtools → Application → Cookies
                                  # or Local Storage depending on your setup

Then run:

    python backend/scripts/byok_verify.py

The script will walk you through the rest.

Never paste real API keys into this script. It only reads public /ai-config
state and counters. Your Anthropic / OpenAI key never leaves your browser.
"""
from __future__ import annotations

import json
import os
import sys
import time
from typing import Any
from urllib import error, request


API_BASE = os.environ.get("PERIGEE_API", "").rstrip("/")
TOKEN = os.environ.get("PERIGEE_TOKEN", "")


def _fail(msg: str) -> None:
    print(f"\n❌ {msg}", file=sys.stderr)
    sys.exit(1)


def _get(path: str) -> dict[str, Any]:
    req = request.Request(
        f"{API_BASE}/api/v1{path}",
        headers={"Authorization": f"Bearer {TOKEN}", "Accept": "application/json"},
    )
    try:
        with request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode())
    except error.HTTPError as e:
        _fail(f"GET {path} → HTTP {e.code}: {e.read().decode()[:200]}")
    except Exception as e:
        _fail(f"GET {path} failed: {e!r}")
    return {}  # unreachable


def _pretty(title: str, data: dict[str, Any]) -> None:
    print(f"\n── {title} ──")
    for k, v in data.items():
        if v is None or v == "":
            continue
        if k.endswith("_encrypted"):
            continue
        print(f"  {k}: {v}")


def main() -> None:
    if not API_BASE:
        _fail("PERIGEE_API env var is not set")
    if not TOKEN:
        _fail("PERIGEE_TOKEN env var is not set (get from devtools → Auth)")

    print(f"Target: {API_BASE}")

    # ------------------------------------------------------------------
    # Step 1: snapshot current AI config
    # ------------------------------------------------------------------
    cfg = _get("/ai-config")
    _pretty("AI config", cfg)

    is_byok = bool(cfg.get("is_key_valid") and cfg.get("has_byok_key"))
    if is_byok:
        print(
            f"\n✓ BYOK is ACTIVE: provider={cfg.get('provider')} "
            f"effective={cfg.get('effective_provider')}/{cfg.get('effective_model')}"
        )
        print("  Expected outcome: platform token counters SHOULD NOT change.")
    else:
        print("\n⚠ BYOK is NOT active. Usage will be metered against platform plan.")
        print("  Expected outcome: platform token counters WILL increase.")

    # ------------------------------------------------------------------
    # Step 2: snapshot usage counters (before)
    # ------------------------------------------------------------------
    before = _get("/ai-config/usage")
    _pretty("Usage — BEFORE", before)

    before_in = int(before.get("current_period_input_tokens") or 0)
    before_out = int(before.get("current_period_output_tokens") or 0)
    before_calls = int(before.get("current_period_llm_calls") or 0)

    # ------------------------------------------------------------------
    # Step 3: prompt user to send a chat
    # ------------------------------------------------------------------
    print(
        "\n──────────────────────────────────────────────────────────────────"
    )
    print("Now send a chat message in the Perigee UI.")
    print("Use one that will reach the ambiguous-tier topic classifier, e.g.:")
    print('  "What do you know about the Westchester multifamily market?"')
    print("Wait for the full response (including any specialist handoffs).")
    print("Then press Enter here.")
    print(
        "──────────────────────────────────────────────────────────────────"
    )
    try:
        input()
    except (EOFError, KeyboardInterrupt):
        print("\naborted")
        sys.exit(1)

    # Small grace period — token recording is awaited but DB commit can lag
    time.sleep(2)

    # ------------------------------------------------------------------
    # Step 4: snapshot usage counters (after)
    # ------------------------------------------------------------------
    after = _get("/ai-config/usage")
    _pretty("Usage — AFTER", after)

    after_in = int(after.get("current_period_input_tokens") or 0)
    after_out = int(after.get("current_period_output_tokens") or 0)
    after_calls = int(after.get("current_period_llm_calls") or 0)

    delta_in = after_in - before_in
    delta_out = after_out - before_out
    delta_calls = after_calls - before_calls

    print("\n── Delta ──")
    print(f"  input_tokens:  +{delta_in}")
    print(f"  output_tokens: +{delta_out}")
    print(f"  llm_calls:     +{delta_calls}")

    # ------------------------------------------------------------------
    # Step 5: verdict
    # ------------------------------------------------------------------
    print("\n── Verdict ──")
    if is_byok:
        if delta_in == 0 and delta_out == 0 and delta_calls == 0:
            print("✅ PASS — BYOK active, zero platform tokens recorded.")
            print("   Confirm tokens DID land on your provider dashboard:")
            print(f"     • Anthropic: https://console.anthropic.com/settings/billing")
            print(f"     • OpenAI:    https://platform.openai.com/usage")
        else:
            print(
                "❌ FAIL — BYOK is active but platform token counters still moved."
            )
            print(
                "   Something in the call path is still using the platform key."
            )
            print(
                "   Tail backend logs for `byok=false` while `has_byok_key=true`."
            )
            sys.exit(2)
    else:
        if delta_in > 0 or delta_out > 0:
            print("✅ PASS — no BYOK, tokens recorded against platform as expected.")
        else:
            print("⚠ UNEXPECTED — no BYOK and no tokens recorded either.")
            print("   Did the chat message actually get a response?")
            sys.exit(2)


if __name__ == "__main__":
    main()
