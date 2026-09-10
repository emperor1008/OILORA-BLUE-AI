"""
Oilora Blue AI — Copernicus Sentinel-1 Catalogue Search

Metadata-level discovery against the official Copernicus Data Space Ecosystem
STAC API (https://stac.dataspace.copernicus.eu/v1/). Public metadata search
requires no credentials; product *download* does (handled by the backend in a
later gate, never by the frontend).

Honesty rules
-------------
* A catalogue match confirms the area was observed. It never proves oil is
  visible, and it never implies a product was downloaded.
* Only real STAC items are returned — never synthesized product identifiers.
* Queries are rate-limited in-process and time-boxed to fail fast.
"""

from __future__ import annotations

import logging
import threading
import time
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx

logger = logging.getLogger("oilora_blue.satellite")

STAC_BASE = "https://stac.dataspace.copernicus.eu/v1"
SEARCH_URL = f"{STAC_BASE}/search"
COLLECTION_GRD = "sentinel-1-grd"

# Metadata search is public; downloads require CDSE authentication (backend).
AUTH_NOTE = (
    "Catalogue metadata search is public. Downloading a product requires a "
    "Copernicus Data Space account configured on the backend."
)

_SEARCH_LOCK = threading.Lock()
# Simple in-process rate limit: at most MAX_SEARCHES any recent WINDOW.
_RATE_WINDOW_SECONDS = 600
_MAX_SEARCHES_WINDOW = 30
_hits: list[float] = []


def _rate_limited() -> bool:
    """Return True when the in-process satellite search budget is exhausted."""
    global _hits
    now = time.monotonic()
    with _SEARCH_LOCK:
        _hits = [t for t in _hits if now - t < _RATE_WINDOW_SECONDS]
        if len(_hits) >= _MAX_SEARCHES_WINDOW:
            return True
        _hits.append(now)
        return False


def _incident_ref_time(incident_start: str | None) -> datetime:
    """Reference time for an incident: the reported date at 12:00 UTC.

    NOAA open dates are calendar dates; comparing scene times against the
    date's midpoint keeps the reported 'time difference' intuitive.
    """
    now = datetime.now(UTC)
    if not incident_start:
        return now
    try:
        dt = datetime.fromisoformat(incident_start)
    except ValueError:
        return now
    return dt.replace(hour=12, minute=0, second=0, microsecond=0)


def search_incident(
    incident: dict[str, Any],
    *,
    window_days: int = 3,
    acquisition_mode: str = "IW",
    processing_level: str = "GRD",
    polarization: str | None = None,
    limit: int = 20,
    timeout_seconds: float = 25.0,
) -> dict[str, Any]:
    """Search Sentinel-1 GRD metadata around an incident location/time.

    Returns a structured result: real matches, provider/limitation notes, and
    an access note. Raises ``ValueError`` for unusable input and typed errors
    (as HTTPException-shaped dicts) for provider failures.
    """
    if incident.get("latitude") is None or incident.get("longitude") is None:
        raise ValueError(
            "This incident has no source-reported coordinates, so a satellite "
            "search cannot be positioned."
        )
    if incident.get("start_time_utc") is None:
        raise ValueError(
            "This incident has no source-reported date, so a satellite search "
            "window cannot be built."
        )
    if window_days < 1 or window_days > 30:
        raise ValueError("window_days must be between 1 and 30.")
    if limit < 1 or limit > 50:
        raise ValueError("limit must be between 1 and 50.")
    if _rate_limited():
        return {
            "status": "rate_limited",
            "message": "Satellite catalogue search is temporarily rate-limited. Try again shortly.",
            "matches": [],
            "provider": "Copernicus Data Space Ecosystem",
            "collection": COLLECTION_GRD,
            "searched_at": datetime.now(UTC).isoformat(),
            "access_note": AUTH_NOTE,
            "warning": (
                "Catalogue matches confirm the area was observed by Sentinel-1. "
                "They do not prove oil is visible in any image."
            ),
        }

    lat = float(incident["latitude"])
    lon = float(incident["longitude"])
    ref_time = _incident_ref_time(incident.get("start_time_utc"))
    start = ref_time - timedelta(days=window_days)
    end = ref_time + timedelta(days=window_days)

    # Search footprint around the incident (approx. 25 km box by default). The
    # STAC bbox intersects satellite footprints; SAR swaths are far larger.
    half = 0.25
    west = max(-180.0, lon - half)
    east = min(180.0, lon + half)
    south = max(-90.0, lat - half)
    north = min(90.0, lat + half)
    bbox = [west, south, east, north]

    body: dict[str, Any] = {
        "collections": [COLLECTION_GRD],
        "datetime": f"{start.strftime('%Y-%m-%dT%H:%M:%SZ')}/{end.strftime('%Y-%m-%dT%H:%M:%SZ')}",
        "bbox": bbox,
        "limit": min(limit * 2 + 5, 100),
        "sortby": [{"field": "datetime", "direction": "desc"}],
    }

    try:
        with httpx.Client(timeout=timeout_seconds, follow_redirects=True) as client:
            response = client.post(SEARCH_URL, json=body)
    except httpx.TimeoutException:
        return {
            "status": "error",
            "error_category": "timeout",
            "message": "Copernicus catalogue did not respond in time. Try again later.",
            "matches": [],
            "provider": "Copernicus Data Space Ecosystem",
            "searched_at": datetime.now(UTC).isoformat(),
            "access_note": AUTH_NOTE,
        }
    except httpx.RequestError:
        return {
            "status": "error",
            "error_category": "network",
            "message": "Copernicus catalogue is unreachable. Check the internet connection.",
            "matches": [],
            "provider": "Copernicus Data Space Ecosystem",
            "searched_at": datetime.now(UTC).isoformat(),
            "access_note": AUTH_NOTE,
        }

    if response.status_code == 429:
        return {
            "status": "rate_limited",
            "message": "The Copernicus catalogue rate-limited this request. Try again shortly.",
            "matches": [],
            "provider": "Copernicus Data Space Ecosystem",
            "searched_at": datetime.now(UTC).isoformat(),
            "access_note": AUTH_NOTE,
        }
    if response.status_code != 200:
        return {
            "status": "error",
            "error_category": "http",
            "code": response.status_code,
            "message": "Copernicus catalogue returned an unexpected response.",
            "matches": [],
            "provider": "Copernicus Data Space Ecosystem",
            "searched_at": datetime.now(UTC).isoformat(),
            "access_note": AUTH_NOTE,
        }

    try:
        payload = response.json()
        features = payload.get("features") or []
    except ValueError:
        return {
            "status": "error",
            "error_category": "invalid_response",
            "message": "Copernicus catalogue returned unreadable data.",
            "matches": [],
            "provider": "Copernicus Data Space Ecosystem",
            "searched_at": datetime.now(UTC).isoformat(),
            "access_note": AUTH_NOTE,
        }

    matches: list[dict[str, Any]] = []
    for feature in features:
        props = feature.get("properties") or {}
        mode = props.get("sar:instrument_mode")
        level_tag = str(props.get("product:type") or "")
        polarizations = props.get("sar:polarizations") or []

        # Post-filter to the requested acquisition mode / processing level.
        if acquisition_mode and mode != acquisition_mode:
            continue
        if processing_level and processing_level.upper() not in level_tag.upper():
            continue
        if polarization:
            requested = polarization.upper().replace(" ", "")
            available = {("".join(str(p).upper().split())) for p in polarizations}
            if (
                requested != "ANY"
                and requested not in available
                and requested
                not in {
                    "VVVH",
                    "VV+VH",
                }
            ):
                # A combined dual-polarization request is satisfied by a dual
                # product containing both channels.
                dual = any("VV" in a and "VH" in a for a in available)
                if not (requested in ("VVVH", "VV+VH") and dual):
                    continue

        item_id = feature.get("id")
        if not item_id:
            continue
        start_dt = props.get("start_datetime") or props.get("datetime")
        end_dt = props.get("end_datetime") or start_dt
        try:
            temporal_distance_hours = (
                (abs((datetime.fromisoformat(start_dt) - ref_time).total_seconds()) / 3600.0)
                if start_dt
                else None
            )
        except (ValueError, TypeError):
            temporal_distance_hours = None

        # Product identifier: for GRD items the STAC id is the Sentinel-1
        # product identifier (optionally suffixed with _COG for cloud-optimized
        # artefacts). Strip the _COG suffix for the canonical product id.
        product_identifier = str(item_id).removesuffix("_COG")

        geometry = feature.get("geometry")
        bbox_feature = feature.get("bbox")
        matches.append(
            {
                "item_id": str(item_id),
                "product_identifier": product_identifier,
                "platform": props.get("platform"),
                "collection": feature.get("collection") or COLLECTION_GRD,
                "acquisition_start": start_dt,
                "acquisition_end": end_dt,
                "acquisition_mode": mode,
                "processing_level": str(props.get("processing:level") or level_tag),
                "polarizations": list(polarizations),
                "orbit_direction": props.get("sat:orbit_state"),
                "absolute_orbit": props.get("sat:absolute_orbit"),
                "geometry_geojson": geometry,
                "bbox": bbox_feature,
                "metadata_url": next(
                    (
                        link.get("href")
                        for link in feature.get("links") or []
                        if link.get("rel") == "self"
                    ),
                    None,
                ),
                "asset_access_status": "metadata_only",
                "temporal_distance_hours": round(temporal_distance_hours, 1)
                if temporal_distance_hours is not None
                else None,
            }
        )
        if len(matches) >= limit:
            break

    return {
        "status": "ok",
        "message": (
            "Catalogue matches confirm the area was observed by Sentinel-1. "
            "They do not prove oil is visible in any image."
        ),
        "matches": matches,
        "match_count": len(matches),
        "provider": "Copernicus Data Space Ecosystem",
        "collection": COLLECTION_GRD,
        "search_bbox": bbox,
        "window_days": window_days,
        "searched_at": datetime.now(UTC).isoformat(),
        "access_note": AUTH_NOTE,
        "documentation_url": "https://stac.dataspace.copernicus.eu/v1/",
    }
