"""Unit tests for the /places/autocomplete proxy.

Pure unit tests in the repo's no-TestClient style: the handler is called
directly with a stub user and httpx patched at the module boundary. What
matters: key-missing degrades to enabled=false, upstream shapes map to
suggestions, and upstream failures NEVER raise (the input is an assist).
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.api.places import autocomplete_address

_USER = SimpleNamespace(id="u-1", email="t@example.com")


def _mock_httpx_client(json_payload: dict | None = None, exc: Exception | None = None):
    """AsyncClient context-manager stub whose .get returns a canned response."""
    response = MagicMock()
    response.raise_for_status = MagicMock()
    response.json = MagicMock(return_value=json_payload or {})

    client = MagicMock()
    if exc is not None:
        client.get = AsyncMock(side_effect=exc)
    else:
        client.get = AsyncMock(return_value=response)

    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=client)
    ctx.__aexit__ = AsyncMock(return_value=False)
    return ctx, client


@pytest.mark.asyncio
async def test_no_api_key_reports_disabled():
    with patch("app.api.places.settings") as settings_mock:
        settings_mock.google_places_api_key = ""
        out = await autocomplete_address(_USER, q="29 lovell ave")
    assert out.enabled is False
    assert out.suggestions == []


@pytest.mark.asyncio
async def test_predictions_map_to_suggestions():
    payload = {
        "status": "OK",
        "predictions": [
            {
                "description": "29 Lovell Avenue, Mill Valley, CA, USA",
                "place_id": "pid-1",
                "structured_formatting": {
                    "main_text": "29 Lovell Avenue",
                    "secondary_text": "Mill Valley, CA, USA",
                },
            },
            {"description": "", "place_id": "pid-skipped"},  # dropped: no text
        ],
    }
    ctx, client = _mock_httpx_client(payload)
    with (
        patch("app.api.places.settings") as settings_mock,
        patch("app.api.places.httpx.AsyncClient", return_value=ctx),
    ):
        settings_mock.google_places_api_key = "k"
        out = await autocomplete_address(_USER, q="29 lovell")

    assert out.enabled is True
    assert [s.place_id for s in out.suggestions] == ["pid-1"]
    s = out.suggestions[0]
    assert s.main_text == "29 Lovell Avenue"
    assert s.secondary_text == "Mill Valley, CA, USA"
    # The key must be sent to Google, never echoed back in the response body.
    sent_params = client.get.await_args.kwargs["params"]
    assert sent_params["key"] == "k"
    assert sent_params["types"] == "address"


@pytest.mark.asyncio
async def test_upstream_error_returns_empty_not_raise():
    ctx, _ = _mock_httpx_client(exc=RuntimeError("network down"))
    with (
        patch("app.api.places.settings") as settings_mock,
        patch("app.api.places.httpx.AsyncClient", return_value=ctx),
    ):
        settings_mock.google_places_api_key = "k"
        out = await autocomplete_address(_USER, q="29 lovell")
    assert out.enabled is True
    assert out.suggestions == []


@pytest.mark.asyncio
async def test_denied_status_returns_empty():
    ctx, _ = _mock_httpx_client({"status": "REQUEST_DENIED"})
    with (
        patch("app.api.places.settings") as settings_mock,
        patch("app.api.places.httpx.AsyncClient", return_value=ctx),
    ):
        settings_mock.google_places_api_key = "k"
        out = await autocomplete_address(_USER, q="29 lovell")
    assert out.enabled is True
    assert out.suggestions == []
