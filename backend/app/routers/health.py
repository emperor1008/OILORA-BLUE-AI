"""
Oilora Blue AI — Health & System Status API

Endpoints for health checks and system readiness.
"""

import os
import shutil

from fastapi import APIRouter

from .. import config
from ..database import get_connection
from ..models.common import BaseResponse, SystemStatus

router = APIRouter(tags=["health"])


@router.get("/api/health", response_model=BaseResponse)
async def health_check():
    """Basic health check endpoint."""
    return BaseResponse(
        success=True,
        message="Oilora Blue AI is running",
        data={"version": config.settings.APP_VERSION},
    )


@router.get("/api/system/status", response_model=BaseResponse)
async def system_status():
    """Detailed system readiness status."""
    # Check database
    try:
        conn = get_connection()
        conn.execute("SELECT 1")
        db_status = "connected"
    except Exception:
        db_status = "disconnected"

    # Check model availability
    model_available = False
    model_checksum = None
    model_path = os.path.join(config.settings.MODELS_DIR, "oil_spill_unet_v1.onnx")
    if os.path.exists(model_path):
        model_available = True
        try:
            from ..services.file_service import FileService

            model_checksum = FileService.compute_sha256(model_path)
        except Exception:
            pass

    # Check disk space
    try:
        disk = shutil.disk_usage(config.settings.DATA_DIR)
        disk_gb = disk.free / (1024**3)
    except Exception:
        disk_gb = 0.0

    status = SystemStatus(
        backend_status="healthy",
        database_status=db_status,
        model_available=model_available,
        model_checksum=model_checksum,
        disk_space_gb=round(disk_gb, 2),
        offline_ready=model_available,
        app_version=config.settings.APP_VERSION,
        local_demo_mode=config.settings.ENABLE_LOCAL_DEMO_MODE,
    )

    return BaseResponse(success=True, data=status.model_dump())
