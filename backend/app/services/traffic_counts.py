"""Traffic counts (AADT / vehicles-per-day) for a property, from free public
state-DOT ArcGIS layers.

Brokers want "how many cars drive past this property a day" — Annual Average
Daily Traffic. There's no single national API, so this is a small provider
abstraction over state-DOT ArcGIS REST feature layers: given a property's
coordinates we run a spatial point-buffer query against the right state's layer
and return the nearest count (vehicles/day + road + year + distance).

Design notes:
- **Synchronous + free** — a single ArcGIS REST `/query` (no API key, no async
  job, no CSV upload), so it works as a live chat tool *and* a property card.
- **Real or nothing** — outside a wired state, or with no nearby station, it
  returns ``None`` and the caller says so plainly. It never fabricates a number.
- **Add a state by config** — drop an ``AadtProvider`` into ``_PROVIDERS``. The
  national HPMS layer (USDOT/Living Atlas) is the natural next provider for
  broad coverage.

The pure helpers (distance, field extraction, formatting) are unit-tested; the
live ArcGIS query needs network so it's exercised separately.
"""

from __future__ import annotations

import logging
import math
import re
from dataclasses import dataclass, field

import httpx

logger = logging.getLogger(__name__)

_QUERY_TIMEOUT_SECONDS = 8.0
# Expanding search radii (miles) — stop at the first radius that yields a count.
_SEARCH_RADII_MI = (0.5, 1.0, 3.0)


@dataclass(frozen=True)
class AadtProvider:
    """One state-DOT AADT ArcGIS layer + how to read a count out of it."""

    name: str
    states: frozenset[str]
    layer_url: str  # an ArcGIS REST FeatureServer/MapServer layer (…/0)
    source_label: str
    # Direct value fields, tried in order; the max present wins (handles
    # directional Back/Ahead counts). Ignored when ``year_column_prefix`` is set.
    aadt_fields: tuple[str, ...] = ()
    # Per-year column mode (e.g. NCDOT's AADT_2022): pick the latest column with
    # a value; the year comes from the column name.
    year_column_prefix: str | None = None
    road_fields: tuple[str, ...] = ()
    desc_fields: tuple[str, ...] = ()
    route_prefix: str = ""  # e.g. "CA-" when the road field is a bare route number
    default_year: int | None = None


# Wired states (fields confirmed against each live layer). Extend here.
_PROVIDERS: tuple[AadtProvider, ...] = (
    AadtProvider(
        name="Caltrans",
        states=frozenset({"CA"}),
        layer_url="https://caltrans-gis.dot.ca.gov/arcgis/rest/services/CHhighway/Traffic_AADT/FeatureServer/0",
        source_label="Caltrans",
        aadt_fields=("AHEAD_AADT", "BACK_AADT"),
        road_fields=("RTE",),
        desc_fields=("DESCRIPTION",),
        route_prefix="CA-",
    ),
    AadtProvider(
        name="NCDOT",
        states=frozenset({"NC"}),
        layer_url="https://services.arcgis.com/NuWFvHYDMVmmxMeM/ArcGIS/rest/services/NCDOT_AADT_Stations/FeatureServer/0",
        source_label="NCDOT",
        year_column_prefix="AADT_",
        road_fields=("ROUTE",),
    ),
    AadtProvider(
        name="VDOT",
        states=frozenset({"VA"}),
        layer_url="https://services.arcgis.com/p5v98VHDX9Atv3l7/arcgis/rest/services/VDOT_Traffic_Volume_2024/FeatureServer/0",
        source_label="VDOT",
        # ADT is the daily average (the AADT equivalent); AAWDT is weekday-only
        # (a different, higher metric) so we deliberately don't mix it in.
        aadt_fields=("ADT",),
        road_fields=("ROUTE_COMMON_NAME", "ROUTE_NAME"),
        default_year=2024,
    ),
)


@dataclass
class TrafficCount:
    aadt: int
    road: str
    year: int | None
    distance_mi: float
    source: str
    state: str | None = None
    nearby: list[int] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "aadt": self.aadt,
            "road": self.road,
            "year": self.year,
            "distance_mi": self.distance_mi,
            "source": self.source,
            "state": self.state,
        }


def provider_for_state(state: str | None) -> AadtProvider | None:
    if not state:
        return None
    st = state.strip().upper()
    for p in _PROVIDERS:
        if st in p.states:
            return p
    return None


def covered_states() -> list[str]:
    return sorted({s for p in _PROVIDERS for s in p.states})


# --------------------------------------------------------------------------- #
# Pure helpers (unit-tested)
# --------------------------------------------------------------------------- #
def _haversine_mi(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    r = 3958.7613  # earth radius, miles
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(min(1.0, math.sqrt(a)))


def _geometry_distance_mi(geom: dict | None, lat: float, lng: float) -> float | None:
    """Min distance (miles) from (lat,lng) to an ArcGIS point/polyline/polygon."""
    if not geom:
        return None
    pts: list[tuple[float, float]] = []
    if "x" in geom and "y" in geom and geom["x"] is not None:
        pts = [(geom["y"], geom["x"])]
    elif "paths" in geom:
        pts = [(pt[1], pt[0]) for path in geom["paths"] for pt in path if len(pt) >= 2]
    elif "rings" in geom:
        pts = [(pt[1], pt[0]) for ring in geom["rings"] for pt in ring if len(pt) >= 2]
    if not pts:
        return None
    return min(_haversine_mi(lat, lng, plat, plng) for plat, plng in pts)


def _to_int(value: object) -> int | None:
    if value is None:
        return None
    try:
        n = int(round(float(value)))
    except (TypeError, ValueError):
        return None
    return n if n > 0 else None


def _extract_aadt(attrs: dict, provider: AadtProvider) -> tuple[int | None, int | None]:
    """Return (aadt, year) for one feature's attributes, or (None, None)."""
    if provider.year_column_prefix:
        prefix = provider.year_column_prefix.upper()
        best_year: int | None = None
        best_val: int | None = None
        for key, raw in attrs.items():
            if not key.upper().startswith(prefix):
                continue
            m = re.search(r"(\d{4})", key)
            val = _to_int(raw)
            if m and val is not None:
                year = int(m.group(1))
                if best_year is None or year > best_year:
                    best_year, best_val = year, val
        return best_val, best_year

    vals = [v for f in provider.aadt_fields if (v := _to_int(attrs.get(f))) is not None]
    return (max(vals) if vals else None), provider.default_year


def _extract_road(attrs: dict, provider: AadtProvider) -> str:
    road = ""
    for f in provider.road_fields:
        v = attrs.get(f)
        if v is not None and str(v).strip():
            road = str(v).strip()
            if provider.route_prefix and not road.upper().startswith(
                provider.route_prefix.upper()
            ):
                road = f"{provider.route_prefix}{road}"
            break
    desc = ""
    for f in provider.desc_fields:
        v = attrs.get(f)
        if v is not None and str(v).strip():
            desc = str(v).strip().title()
            break
    if road and desc:
        return f"{road} ({desc})"
    return road or desc or "a nearby road"


def pick_nearest(
    features: list[dict], lat: float, lng: float, provider: AadtProvider
) -> TrafficCount | None:
    """Pick the nearest feature that carries a usable AADT value."""
    best: TrafficCount | None = None
    others: list[int] = []
    for feat in features:
        attrs = feat.get("attributes") or {}
        aadt, year = _extract_aadt(attrs, provider)
        if aadt is None:
            continue
        dist = _geometry_distance_mi(feat.get("geometry"), lat, lng)
        dist = round(dist, 2) if dist is not None else 0.0
        if best is None or dist < best.distance_mi:
            if best is not None:
                others.append(best.aadt)
            best = TrafficCount(
                aadt=aadt,
                road=_extract_road(attrs, provider),
                year=year,
                distance_mi=dist,
                source=provider.source_label,
            )
        else:
            others.append(aadt)
    if best is not None:
        best.nearby = sorted(others, reverse=True)[:3]
    return best


def format_traffic_summary(tc: TrafficCount | None, state: str | None = None) -> str:
    """One-line, broker-friendly summary (also used in the report + agent)."""
    if tc is None:
        if state and provider_for_state(state) is None:
            cov = ", ".join(covered_states())
            return (
                f"No automated traffic-count source is wired for {state.upper()} yet "
                f"(currently covered: {cov})."
            )
        return "No traffic-count station was found near this address."
    yr = f" {tc.year}" if tc.year else ""
    dist = "at the site" if tc.distance_mi <= 0.05 else f"{tc.distance_mi} mi away"
    return f"~{tc.aadt:,} vehicles/day on {tc.road} ({tc.source}{yr}, {dist})"


# --------------------------------------------------------------------------- #
# Live query
# --------------------------------------------------------------------------- #
async def _query(
    provider: AadtProvider, lat: float, lng: float, radius_mi: float
) -> list[dict]:
    params = {
        "geometry": f"{lng},{lat}",
        "geometryType": "esriGeometryPoint",
        "inSR": "4326",
        "spatialRel": "esriSpatialRelIntersects",
        "distance": str(radius_mi),
        "units": "esriSRUnit_StatuteMile",
        "outFields": "*",
        "returnGeometry": "true",
        "outSR": "4326",
        "resultRecordCount": "50",
        "f": "json",
    }
    try:
        async with httpx.AsyncClient(timeout=_QUERY_TIMEOUT_SECONDS) as client:
            resp = await client.get(f"{provider.layer_url}/query", params=params)
            resp.raise_for_status()
            return resp.json().get("features", []) or []
    except Exception as exc:  # noqa: BLE001 - degrade to "no data", never raise
        logger.warning(
            "[traffic_counts] %s query failed: %s", provider.name, type(exc).__name__
        )
        return []


async def get_traffic_count(
    lat: float, lng: float, state: str | None
) -> TrafficCount | None:
    """Nearest AADT count for a location, or ``None`` if uncovered / not found."""
    provider = provider_for_state(state)
    if provider is None:
        return None
    for radius in _SEARCH_RADII_MI:
        features = await _query(provider, lat, lng, radius)
        best = pick_nearest(features, lat, lng, provider)
        if best is not None:
            best.state = (state or "").upper() or None
            return best
    return None
