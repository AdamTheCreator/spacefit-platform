"""One-time authorization codes for the OAuth login handoff.

The Google callback used to 302-redirect with ``?access_token=…&refresh_token=…``
in the URL, which leaks tokens into browser history, referrer headers, and any
proxy/access log. Instead the callback stores the freshly minted tokens against
a short-lived, single-use code and redirects with only that code; the SPA
exchanges it for the tokens via a POST.

In-memory + per-process (single-use, ~60s TTL). Fine for a single uvicorn
worker; **swap for Redis when scaling horizontally** — otherwise a code minted
on one worker can't be redeemed on another.
"""

from __future__ import annotations

import secrets
import threading
import time
from dataclasses import dataclass

_CODE_TTL_SECONDS = 60


@dataclass
class _Entry:
    access_token: str
    refresh_token: str
    expires_in: int
    created_at: float


class OAuthCodeStore:
    def __init__(self) -> None:
        self._store: dict[str, _Entry] = {}
        self._lock = threading.Lock()

    def _purge(self, now: float) -> None:
        expired = [
            code
            for code, entry in self._store.items()
            if now - entry.created_at > _CODE_TTL_SECONDS
        ]
        for code in expired:
            self._store.pop(code, None)

    def issue(self, access_token: str, refresh_token: str, expires_in: int) -> str:
        code = secrets.token_urlsafe(32)
        now = time.monotonic()
        with self._lock:
            self._purge(now)
            self._store[code] = _Entry(
                access_token=access_token,
                refresh_token=refresh_token,
                expires_in=expires_in,
                created_at=now,
            )
        return code

    def redeem(self, code: str) -> _Entry | None:
        now = time.monotonic()
        with self._lock:
            self._purge(now)
            entry = self._store.pop(code, None)  # single-use
        if entry is None:
            return None
        if now - entry.created_at > _CODE_TTL_SECONDS:
            return None
        return entry


oauth_code_store = OAuthCodeStore()
