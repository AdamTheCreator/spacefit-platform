"""Tests for the public sales-lead capture endpoint."""

from __future__ import annotations

from app.api.sales import _IPRateLimiter


class TestIPRateLimiter:
    def test_allows_under_limit(self) -> None:
        rl = _IPRateLimiter()
        assert rl.check("1.2.3.4", limit=3, window_seconds=600) is True
        assert rl.check("1.2.3.4", limit=3, window_seconds=600) is True
        assert rl.check("1.2.3.4", limit=3, window_seconds=600) is True

    def test_blocks_over_limit(self) -> None:
        rl = _IPRateLimiter()
        for _ in range(3):
            rl.check("1.2.3.4", limit=3, window_seconds=600)
        assert rl.check("1.2.3.4", limit=3, window_seconds=600) is False

    def test_isolated_per_ip(self) -> None:
        rl = _IPRateLimiter()
        for _ in range(3):
            rl.check("1.1.1.1", limit=3, window_seconds=600)
        # Different IP should still be allowed.
        assert rl.check("2.2.2.2", limit=3, window_seconds=600) is True
