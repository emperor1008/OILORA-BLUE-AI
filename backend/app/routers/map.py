"""
Oilora Blue AI — Interactive Map API

Real-data endpoints backing the maritime intelligence map workspace.

All feature data returned here is derived from genuine registered files and
SQLite case state. Layers whose scientific stage has not run are reported with
typed non-ready states and reasons - never fabricated geometry.
"""

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import Response

from ..models.common import BaseResponse
from ..models.map import ViewportState
from ..services.map_service import map_service

router = APIRouter(prefix="/api/cases/{case_id}/map", tags=["map"])


def _require_case(case_id: str):
    case = map_service.get_case_or_404(case_id)
    if case is None:
        raise HTTPException(status_code=404, detail=f"Case not found: {case_id}")
    return case


@router.get("/summary", response_model=BaseResponse)
async def map_summary(case_id: str):
    """Map-readiness summary derived from genuine case and file state."""
    case = _require_case(case_id)
    return BaseResponse(success=True, data=map_service.build_summary(case))


@router.get("/layers", response_model=BaseResponse)
async def map_layers(case_id: str):
    """Typed layer registry with honest availability for this case."""
    case = _require_case(case_id)
    return BaseResponse(
        success=True, data={"case_id": case_id, "layers": map_service.build_layers(case)}
    )


@router.get("/features", response_model=BaseResponse)
async def map_features(
    case_id: str,
    layer: str = Query("", description="Comma-separated layer ids, or empty for all vector layers"),
):
    """
    Real GeoJSON features for vector layers.

    A layer with no genuine data returns a typed non-ready state (not_processed /
    missing_input / failed) with null features instead of a misleading empty
    collection. Raster layers are served separately (see /sar-overlay).
    """
    case = _require_case(case_id)
    requested = [item.strip() for item in layer.split(",") if item.strip()] or None
    try:
        features = map_service.build_features(case, requested)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return BaseResponse(
        success=True,
        data={"case_id": case_id, "layers": features},
    )


@router.get("/provenance", response_model=BaseResponse)
async def map_provenance(case_id: str):
    """Source dataset + derived artifact provenance (no filesystem paths)."""
    _require_case(case_id)
    return BaseResponse(success=True, data=map_service.build_provenance(case_id))


@router.get("/viewport", response_model=BaseResponse)
async def get_viewport(case_id: str):
    """Saved analyst viewport plus a data-derived default (safe preferences only)."""
    _require_case(case_id)
    return BaseResponse(success=True, data=map_service.get_viewport(case_id))


@router.patch("/viewport", response_model=BaseResponse)
async def save_viewport(case_id: str, viewport: ViewportState):
    """Persist the analyst's current viewport preference."""
    _require_case(case_id)
    data = map_service.save_viewport(case_id, viewport.model_dump())
    return BaseResponse(success=True, message="Viewport saved", data=data)


@router.get("/sar-overlay", response_model=BaseResponse)
async def sar_overlay(case_id: str):
    """
    Derived Sentinel-1 SAR preview descriptor (bounds + image URL + checksums).

    The preview is regenerated from the real uploaded raster whenever the cached
    copy no longer matches the registered input checksum. When generation is not
    possible (missing geospatial runtime, unreadable raster, no CRS) the response
    is honestly marked unavailable.
    """
    _require_case(case_id)
    return BaseResponse(success=True, data=map_service.get_sar_overlay(case_id))


@router.get("/sar-preview/{file_id}")
async def sar_preview_image(case_id: str, file_id: str, request: Request):
    """Serve the derived grayscale SAR preview PNG (image/png)."""
    case = _require_case(case_id)
    _ = case
    png_bytes, reason = map_service.read_sar_preview_bytes(case_id, file_id)
    if png_bytes is None:
        request_id = getattr(request.state, "request_id", None) or "unknown"
        raise HTTPException(
            status_code=404,
            detail={
                "message": reason or "SAR preview unavailable",
                "error_code": "MAP_SAR_PREVIEW_UNAVAILABLE",
                "request_id": request_id,
            },
        )
    return Response(
        content=png_bytes,
        media_type="image/png",
        headers={
            "Cache-Control": "public, max-age=86400",
            "X-Content-Type-Options": "nosniff",
        },
    )
