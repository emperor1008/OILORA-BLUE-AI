"""
Oilora Blue AI — Common Pydantic Models

Shared base models, enums, and response types used across the API.
"""

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

# ─── Enums ────────────────────────────────────────────────────────────


class CaseStatus(str, Enum):
    CREATED = "created"
    DATA_REGISTERED = "data_registered"
    VALIDATING = "validating"
    PROCESSING = "processing"
    AWAITING_REVIEW = "awaiting_review"
    COMPLETED = "completed"
    FAILED = "failed"


class ProcessingStage(str, Enum):
    REGISTRATION = "registration"
    VALIDATION = "validation"
    SAR_PREPROCESSING = "sar_preprocessing"
    OIL_SLICK_DETECTION = "oil_slick_detection"
    HUMAN_REVIEW = "human_review"
    BACKWARD_DRIFT = "backward_drift"
    FORWARD_DRIFT = "forward_drift"
    AIS_ANALYSIS = "ais_analysis"
    CANDIDATE_RANKING = "candidate_ranking"
    EVIDENCE_MANIFEST = "evidence_manifest"
    REPORT_GENERATION = "report_generation"


class FileType(str, Enum):
    SAR = "sar"
    AIS = "ais"
    ENVIRONMENTAL = "environmental"
    MASK = "mask"
    BOUNDARY = "boundary"
    OTHER = "other"


class JobStatus(str, Enum):
    QUEUED = "queued"
    VALIDATING = "validating"
    PROCESSING = "processing"
    AWAITING_REVIEW = "awaiting_review"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


# ─── Base Models ──────────────────────────────────────────────────────


class BaseResponse(BaseModel):
    """Base response model with success flag."""

    success: bool = True
    message: str = ""
    data: Any = None


class ErrorResponse(BaseModel):
    """Error response model."""

    success: bool = False
    message: str
    error_code: str | None = None
    detail: str | None = None


class PaginationParams(BaseModel):
    """Pagination query parameters."""

    offset: int = Field(default=0, ge=0)
    limit: int = Field(default=50, ge=1, le=200)


class PaginatedResponse(BaseResponse):
    """Paginated list response."""

    total: int = 0
    offset: int = 0
    limit: int = 50


# ─── Geometry Models ──────────────────────────────────────────────────


class BoundingBox(BaseModel):
    """Geographic bounding box in WGS 84."""

    min_lat: float = Field(..., ge=-90, le=90)
    min_lon: float = Field(..., ge=-180, le=180)
    max_lat: float = Field(..., ge=-90, le=90)
    max_lon: float = Field(..., ge=-180, le=180)


class GeoPoint(BaseModel):
    """Single geographic point."""

    lat: float = Field(..., ge=-90, le=90)
    lon: float = Field(..., ge=-180, le=180)


# ─── Health & Status Models ───────────────────────────────────────────


class SystemStatus(BaseModel):
    """System readiness information."""

    backend_status: str = "healthy"
    database_status: str = "connected"
    model_available: bool = False
    model_checksum: str | None = None
    dataset_available: bool = False
    disk_space_gb: float = 0.0
    offline_ready: bool = False
    app_version: str = ""
    local_demo_mode: bool = True
