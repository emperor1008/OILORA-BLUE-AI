"""
Oilora Blue AI — Detection Models

Pydantic models for oil-slick detection results and review.
"""

from typing import Any

from pydantic import BaseModel, Field


class DetectionConfig(BaseModel):
    """Configuration for oil-slick detection."""

    threshold: float = Field(default=0.5, ge=0.0, le=1.0)
    model_name: str = "oil_spill_unet_v1"
    min_area_pixels: int = 10
    apply_morphological_filter: bool = True
    smoothing_sigma: float = 0.0


class DetectionResult(BaseModel):
    """Results from oil-slick detection."""

    case_id: str
    job_id: str
    probability_raster_path: str | None = None
    binary_mask_path: str | None = None
    oil_polygons_geojson: dict | None = None
    area_sq_km: float = 0.0
    perimeter_km: float = 0.0
    centroid_lat: float | None = None
    centroid_lon: float | None = None
    orientation_degrees: float | None = None
    fragmentation_index: float = 0.0
    inference_duration_seconds: float = 0.0
    model_name: str = ""
    model_version: str = ""
    model_checksum: str = ""
    threshold_used: float = 0.0
    processing_config: dict[str, Any] = {}
    # Ground-truth metrics (only when ground truth exists)
    precision: float | None = None
    recall: float | None = None
    f1_score: float | None = None
    iou: float | None = None
    dice_coefficient: float | None = None
    confusion_matrix: dict | None = None


class DetectionReview(BaseModel):
    """Analyst review of detection results."""

    case_id: str
    detection_result_id: str
    accepted: bool
    corrected_boundary_geojson: dict | None = None
    threshold_adjusted: float | None = Field(None, ge=0.0, le=1.0)
    review_notes: str = ""
    reviewer: str = "local_analyst"


class DetectionReviewResult(BaseModel):
    """Outcome of detection review."""

    review_id: str
    accepted: bool
    final_boundary_geojson: dict | None = None
    original_prediction_geojson: dict | None = None
    review_timestamp: str
    audit_event_id: int
