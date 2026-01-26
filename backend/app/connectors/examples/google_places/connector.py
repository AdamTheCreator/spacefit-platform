"""
Google Places Connector — API mode example.

Demonstrates a pure-API connector that:
  - Authenticates via API key
  - Executes HTTP requests against the Google Places API
  - Normalizes the response into the declared output schema
  - Returns a standard ConnectorResponse envelope

No browser automation, no workflow YAML.  All logic is in Python.
"""

from __future__ import annotations

import logging
import time
from typing import Any

import httpx

from app.connectors.interface import BaseConnector
from app.connectors.schemas.errors import (
    ConnectorError,
    ErrorCode,
    ErrorSeverity,
)
from app.connectors.schemas.manifest import ConnectorManifest
from app.connectors.schemas.response import (
    ConnectorResponse,
    ErrorDetail,
    Metrics,
    Provenance,
    ResponseStatus,
)
from app.connectors.schemas.task import TaskRequest

logger = logging.getLogger("connectors.google_places")

_BASE_URL = "https://maps.googleapis.com/maps/api/place"


class GooglePlacesConnector(BaseConnector):
    """Pure API connector for Google Places."""

    def __init__(self, manifest: ConnectorManifest) -> None:
        super().__init__(manifest)
        self._api_key: str = ""

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def validate_config(self) -> bool:
        if not self.manifest.allowed_domains:
            raise ConnectorError(
                code=ErrorCode.PLATFORM_CONFIG_INVALID,
                message="Google Places connector requires allowed_domains.",
            )
        return True

    async def authenticate(
        self,
        credentials: dict[str, Any],
        *,
        tenant_id: str,
    ) -> bool:
        api_key = (
            credentials.get("api_key")
            or credentials.get("password")  # Stored as password in SiteCredential
            or ""
        )
        if not api_key:
            raise ConnectorError(
                code=ErrorCode.AUTH_MISSING_CREDENTIALS,
                message="No API key provided for Google Places.",
                severity=ErrorSeverity.PERMANENT,
                remediation="Add a Google Places API key in the Connections page.",
            )
        self._api_key = api_key
        return True

    async def execute(self, request: TaskRequest) -> ConnectorResponse:
        capability = request.capability
        params = request.params
        t0 = time.monotonic()

        try:
            if capability in ("place_details", "business_info"):
                raw = await self._place_details(params)
            elif capability == "nearby_search":
                raw = await self._nearby_search(params)
            elif capability == "geocoding":
                raw = await self._text_search(params)
            else:
                raw = await self._text_search(params)

            data = await self.normalize(raw)
            elapsed_ms = int((time.monotonic() - t0) * 1000)

            return ConnectorResponse(
                task_id=request.task_id,
                trace_id=request.trace_id,
                status=ResponseStatus.SUCCESS,
                data=data,
                provenance=Provenance(
                    source_connector=self.manifest.connector_id,
                    execution_mode="api",
                    pages_visited=[],
                    extraction_summary=f"Fetched {capability} from Google Places API",
                ),
                metrics=Metrics(
                    latency_ms=elapsed_ms,
                    api_calls_made=1,
                ),
            )

        except ConnectorError:
            raise
        except Exception as exc:
            elapsed_ms = int((time.monotonic() - t0) * 1000)
            return ConnectorResponse(
                task_id=request.task_id,
                trace_id=request.trace_id,
                status=ResponseStatus.FAILURE,
                errors=[ErrorDetail(
                    code=ErrorCode.PLATFORM_INTERNAL.value,
                    message=str(exc),
                    severity="error",
                )],
                metrics=Metrics(latency_ms=elapsed_ms),
            )

    async def normalize(self, raw: Any) -> dict[str, Any] | list[Any]:
        """Normalize Google Places API response."""
        if isinstance(raw, dict):
            # Single result (place_details)
            result = raw.get("result", raw)
            return {
                "place_id": result.get("place_id", ""),
                "name": result.get("name", ""),
                "formatted_address": result.get("formatted_address", ""),
                "geometry": result.get("geometry", {}),
                "types": result.get("types", []),
                "rating": result.get("rating"),
                "business_status": result.get("business_status", ""),
                "phone": result.get("formatted_phone_number", ""),
                "website": result.get("website", ""),
                "opening_hours": result.get("opening_hours", {}),
            }
        if isinstance(raw, list):
            return [await self.normalize(item) for item in raw]
        return raw

    async def teardown(self) -> None:
        self._api_key = ""

    # ------------------------------------------------------------------
    # API calls
    # ------------------------------------------------------------------

    async def _text_search(self, params: dict[str, Any]) -> dict:
        query = params.get("query", params.get("address", ""))
        url = f"{_BASE_URL}/textsearch/json"
        return await self._get(url, {"query": query})

    async def _nearby_search(self, params: dict[str, Any]) -> dict:
        url = f"{_BASE_URL}/nearbysearch/json"
        api_params: dict[str, Any] = {}
        if "location" in params:
            api_params["location"] = params["location"]
        elif "lat" in params and "lng" in params:
            api_params["location"] = f"{params['lat']},{params['lng']}"
        api_params["radius"] = params.get("radius", 1000)
        if "type" in params:
            api_params["type"] = params["type"]
        if "keyword" in params:
            api_params["keyword"] = params["keyword"]
        return await self._get(url, api_params)

    async def _place_details(self, params: dict[str, Any]) -> dict:
        place_id = params.get("place_id", "")
        if not place_id:
            # Try text search first to get place_id
            search = await self._text_search(params)
            results = search.get("results", [])
            if not results:
                raise ConnectorError(
                    code=ErrorCode.EXTRACT_NO_DATA,
                    message="No places found for the given query.",
                    severity=ErrorSeverity.PERMANENT,
                )
            place_id = results[0]["place_id"]

        url = f"{_BASE_URL}/details/json"
        fields = params.get(
            "fields",
            "place_id,name,formatted_address,geometry,types,rating,"
            "business_status,formatted_phone_number,website,opening_hours",
        )
        return await self._get(url, {"place_id": place_id, "fields": fields})

    async def _get(
        self,
        url: str,
        params: dict[str, Any],
    ) -> dict:
        params["key"] = self._api_key
        timeout = self.manifest.runtime_limits.max_runtime_seconds

        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.get(url, params=params)

        if resp.status_code == 429:
            raise ConnectorError(
                code=ErrorCode.NET_RATE_LIMITED,
                message="Google Places API rate limit exceeded.",
                severity=ErrorSeverity.TRANSIENT,
            )
        if resp.status_code >= 500:
            raise ConnectorError(
                code=ErrorCode.NET_SERVER_ERROR,
                message=f"Google Places API error: {resp.status_code}",
                severity=ErrorSeverity.TRANSIENT,
            )
        if resp.status_code >= 400:
            raise ConnectorError(
                code=ErrorCode.AUTH_INVALID_CREDENTIALS,
                message=f"Google Places API returned {resp.status_code}: {resp.text[:200]}",
                severity=ErrorSeverity.PERMANENT,
                remediation="Check your Google Places API key.",
            )

        data = resp.json()
        status = data.get("status", "")
        if status == "REQUEST_DENIED":
            raise ConnectorError(
                code=ErrorCode.AUTH_INVALID_CREDENTIALS,
                message=f"API key denied: {data.get('error_message', '')}",
                severity=ErrorSeverity.PERMANENT,
                remediation="Verify your Google Places API key is valid and has Places API enabled.",
            )
        if status == "ZERO_RESULTS":
            raise ConnectorError(
                code=ErrorCode.EXTRACT_NO_DATA,
                message="No results found.",
                severity=ErrorSeverity.PERMANENT,
            )

        return data
