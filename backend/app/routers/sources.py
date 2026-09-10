"""
Oilora Blue AI — Data Source Registry API

Read-only registry listing plus an explicit, safe "test connection" action.
Credential values are never returned — only ``authentication_configured``.
"""

from fastapi import APIRouter, HTTPException

from ..models.common import BaseResponse
from ..services.source_registry import source_registry

router = APIRouter(tags=["sources"])


@router.get("/api/sources", response_model=BaseResponse)
async def list_sources():
    """List every registered data source with its honest current status."""
    sources = source_registry.list_sources()
    return BaseResponse(success=True, data=sources)


@router.get("/api/sources/{source_id}", response_model=BaseResponse)
async def get_source(source_id: str):
    """Get a single source record."""
    source = source_registry.get_source(source_id)
    if source is None:
        raise HTTPException(status_code=404, detail=f"Source not found: {source_id}")
    return BaseResponse(success=True, data=source)


@router.post("/api/sources/{source_id}/test", response_model=BaseResponse)
async def test_source(source_id: str):
    """Run a real, time-limited connectivity probe against the provider.

    The probe respects a short cooldown so repeated calls cannot hammer the
    provider. Local-file-workflow sources report their status without any
    network activity. Credential-gated sources without configured credentials
    report ``authentication_required``.
    """
    source = source_registry.probe_source(source_id, force=True)
    if source is None:
        raise HTTPException(status_code=404, detail=f"Source not found: {source_id}")
    return BaseResponse(
        success=True,
        message=f"Source status: {source['configured_status']}",
        data=source,
    )
