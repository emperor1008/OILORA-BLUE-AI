"""
Oilora Blue AI — Historical Incident Explorer API

Endpoints for the historical-incident exploration interface. Reference data is
kept separate from user investigations. Every response carries only verified,
source-registered facts; nothing is invented to fill gaps.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime

import httpx
from fastapi import APIRouter, Header, HTTPException, Query

from .. import config
from ..models.common import BaseResponse
from ..models.historical import CreateInvestigationRequest, PaginatedIncidentResponse
from ..services.case_service import case_service
from ..services.historical_service import NOAA_DATASET, historical_service
from ..services.satellite_search import search_incident

logger = logging.getLogger("oilora_blue.historical")

router = APIRouter(prefix="/api/historical-incidents", tags=["historical-incidents"])

NOAA_RAW_URL = "https://incidentnews.noaa.gov/raw/incidents.csv"
MAX_PAGE_SIZE = 100
DEFAULT_PAGE_SIZE = 25


def _json_field(value, fallback=None):
    if value is None or value == "":
        return fallback
    try:
        return json.loads(value)
    except (ValueError, TypeError):
        return fallback


@router.get("", response_model=PaginatedIncidentResponse)
async def list_historical_incidents(
    search: str | None = Query(None, max_length=200),
    country: str | None = Query(None, max_length=120),
    category: str | None = Query(None, max_length=40),
    source: str | None = Query(None, max_length=60),
    start_date: str | None = Query(None, description="YYYY-MM-DD"),
    end_date: str | None = Query(None, description="YYYY-MM-DD"),
    verification_status: str | None = Query(None, max_length=40),
    satellite_status: str | None = Query(None, pattern="^(matched|unmatched)$"),
    coordinate_accuracy: str | None = Query(None, max_length=30),
    sort: str = Query("date_desc", pattern="^(date_desc|date_asc|name_asc)$"),
    limit: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
    offset: int = Query(0, ge=0),
    cursor: str | None = Query(None, max_length=120),
):
    """List verified historical incidents with server-side filtering.

    Returns compact map/sidebar summaries only — never full source documents
    or internal paths. Supports offset and keyset-cursor pagination (the
    cursor is only defined for the default date_desc ordering).
    """
    effective_cursor = cursor if sort == "date_desc" else None
    result = historical_service.list_incidents(
        search=search or None,
        country=country or None,
        category=category or None,
        source=source or None,
        start_date=start_date or None,
        end_date=end_date or None,
        verification_status=verification_status or None,
        satellite_status=satellite_status or None,
        coordinate_accuracy=coordinate_accuracy or None,
        sort=sort,
        limit=limit,
        offset=offset,
        cursor=effective_cursor,
    )
    return PaginatedIncidentResponse(
        success=True,
        data=result["items"],
        total=result["total"],
        limit=result["limit"],
        offset=result["offset"],
        next_cursor=result["next_cursor"],
    )


@router.get("/options", response_model=BaseResponse)
async def historical_filter_options():
    """Real distinct values available for each explorer filter."""
    return BaseResponse(
        success=True,
        data=historical_service.filter_options(),
    )


@router.get("/map", response_model=BaseResponse)
async def historical_map(
    west: float = Query(..., ge=-180, le=180),
    south: float = Query(..., ge=-90, le=90),
    east: float = Query(..., ge=-180, le=180),
    north: float = Query(..., ge=-90, le=90),
):
    """Bounded GeoJSON FeatureCollection of incidents with usable coordinates.

    Only incidents with source-reported coordinates are mapped; missing values
    are never replaced with invented points.
    """
    if west >= east:
        raise HTTPException(status_code=422, detail="west must be less than east")
    if south >= north:
        raise HTTPException(status_code=422, detail="south must be less than north")
    if (east - west) > 360.0 or (north - south) > 180.0:
        raise HTTPException(
            status_code=422,
            detail="Requested bounding box exceeds the maximum supported span.",
        )
    features = historical_service.map_features(west, south, east, north)
    return BaseResponse(
        success=True,
        data=features,
        message="Historical incidents within the requested map bounds",
    )


@router.get("/import/runs", response_model=BaseResponse)
async def import_runs(limit: int = Query(10, ge=1, le=50)):
    """Recent historical-source import runs (auditable)."""
    runs = historical_service.list_import_runs(limit)
    return BaseResponse(success=True, data=runs)


@router.post("/import/noaa", response_model=BaseResponse, status_code=201)
async def import_noaa(
    source_url: str = Query(NOAA_RAW_URL),
    limit: int | None = Query(None, ge=1, le=6000),
    x_admin_key: str | None = Header(default=None, alias="X-Admin-Key"),
):
    """Import the NOAA IncidentNews raw CSV (repeatable, idempotent).

    Not a public unprotected endpoint: enabled only in local demo mode or when
    the configured admin key is supplied. Failed later imports never erase
    previously imported incidents.
    """
    admin_key = config.settings.NOAA_IMPORT_ADMIN_KEY
    allowed = config.settings.ENABLE_LOCAL_DEMO_MODE or (
        bool(admin_key) and admin_key == x_admin_key
    )
    if not allowed:
        raise HTTPException(
            status_code=403,
            detail="Import endpoint is disabled. It requires local demo mode "
            "or the configured admin key.",
        )
    if not source_url.startswith("https://incidentnews.noaa.gov/"):
        raise HTTPException(
            status_code=422,
            detail="Only the official NOAA IncidentNews source is permitted.",
        )
    try:
        with httpx.Client(timeout=120.0, follow_redirects=True) as client:
            response = client.get(source_url)
    except httpx.TimeoutException:
        raise HTTPException(
            status_code=504,
            detail="NOAA IncidentNews did not respond in time.",
        ) from None
    except httpx.RequestError:
        raise HTTPException(
            status_code=502,
            detail="NOAA IncidentNews is unreachable.",
        ) from None
    if response.status_code != 200:
        raise HTTPException(
            status_code=502,
            detail=f"NOAA IncidentNews returned HTTP {response.status_code}.",
        ) from None

    result = historical_service.import_noaa_csv(
        response.content,
        source_url=source_url,
        retrieved_at=datetime.now(UTC).isoformat(),
        limit=limit,
    )
    return BaseResponse(
        success=True,
        message="NOAA IncidentNews import completed",
        data=result,
    )


@router.get("/{incident_id}", response_model=BaseResponse)
async def get_historical_incident(incident_id: str):
    """Full normalized incident detail with provenance sections."""
    detail = historical_service.get_incident(incident_id)
    if detail is None:
        raise HTTPException(status_code=404, detail=f"Incident not found: {incident_id}")
    for match in detail.get("satellite_matches", []):
        match["geometry_geojson"] = _json_field(match.get("geometry_geojson"))
        match["bbox"] = _json_field(match.get("bbox"))
        match["polarizations"] = _json_field(match.get("polarizations"), [])
    return BaseResponse(success=True, data=detail)


@router.get("/{incident_id}/sources", response_model=BaseResponse)
async def get_historical_incident_sources(incident_id: str):
    """Sources plus field-level provenance for one incident."""
    detail = historical_service.get_incident(incident_id)
    if detail is None:
        raise HTTPException(status_code=404, detail=f"Incident not found: {incident_id}")
    return BaseResponse(
        success=True,
        data={
            "incident_id": incident_id,
            "sources": detail["sources"],
            "field_provenance": detail["field_provenance"],
            "limitation": (
                detail["sources"][0]["licence_or_usage_note"] if detail["sources"] else None
            ),
        },
    )


@router.get("/{incident_id}/satellite-search", response_model=BaseResponse)
async def satellite_search_for_incident(
    incident_id: str,
    window_days: int = Query(3, ge=1, le=30),
    acquisition_mode: str = Query("IW", max_length=20),
    processing_level: str = Query("GRD", max_length=20),
    polarization: str | None = Query(None, max_length=20),
    limit: int = Query(20, ge=1, le=50),
):
    """Search the real Copernicus Sentinel-1 catalogue around an incident.

    Metadata search only: results are stored as catalogue matches. Nothing is
    downloaded and no claim is made about oil visibility.
    """
    detail = historical_service.get_incident(incident_id)
    if detail is None:
        raise HTTPException(status_code=404, detail=f"Incident not found: {incident_id}")
    try:
        result = search_incident(
            detail,
            window_days=window_days,
            acquisition_mode=acquisition_mode,
            processing_level=processing_level,
            polarization=polarization,
            limit=limit,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None

    if result["status"] == "ok" and result.get("matches"):
        historical_service.store_satellite_matches(incident_id, result["matches"])

    fresh = historical_service.get_incident(incident_id)
    summary = (fresh or detail).get("satellite_summary")
    return BaseResponse(success=True, data={**result, "satellite_summary": summary})


@router.post(
    "/{incident_id}/create-investigation",
    response_model=BaseResponse,
    status_code=201,
)
async def create_investigation_from_incident(incident_id: str, body: CreateInvestigationRequest):
    """Create a working investigation (case) from a historical incident.

    Only source-supported fields are copied. Missing values are never filled
    with invented defaults, and the resulting case is never described as an
    AI detection.
    """
    detail = historical_service.get_incident(incident_id)
    if detail is None:
        raise HTTPException(status_code=404, detail=f"Incident not found: {incident_id}")
    if not body.confirm:
        raise HTTPException(
            status_code=422,
            detail="User confirmation is required to create an investigation.",
        )

    title = detail["canonical_name"] or "Untitled historical incident"
    region = detail["country"] or ""
    summary = (detail.get("summary") or "").strip()
    notes = (
        f"Created from verified historical record {incident_id} "
        f"(source: {NOAA_DATASET}). Only source-supported fields were copied; "
        "coordinate accuracy and provenance are preserved in the original record."
    )
    if body.analyst_notes:
        notes = f"{notes}\nAnalyst notes: {body.analyst_notes}"

    case = case_service.create_case(
        {
            "title": title[:200],
            "description": summary[:2000],
            "region": region[:200],
            "incident_time": detail.get("start_time_utc"),
            "analyst_notes": notes[:5000],
            "historical_incident_id": incident_id,
        }
    )
    return BaseResponse(
        success=True,
        message="Investigation created from historical incident",
        data=case,
    )
