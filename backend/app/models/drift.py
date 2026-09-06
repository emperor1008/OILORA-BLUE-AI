"""
Oilora Blue AI — Drift Models

Pydantic models for backward drift reconstruction and forward drift prediction.
"""

from typing import Any

from pydantic import BaseModel, Field


class DriftConfig(BaseModel):
    """Configuration for drift simulation."""

    simulation_hours: float = Field(
        default=72.0, gt=0, description="Backward simulation duration in hours"
    )
    particle_count: int = Field(default=1000, ge=100, le=10000)
    time_step_minutes: float = Field(default=15.0, gt=0)
    release_time_window_hours: float = Field(default=6.0, gt=0)
    uncertainty_factor: float = Field(default=0.2, ge=0.0, le=1.0)
    random_seed: int | None = None
    ensemble_runs: int = Field(default=3, ge=1, le=10)
    wind_weight: float = Field(default=0.03, ge=0.0, le=0.1)


class DriftResult(BaseModel):
    """Results from drift simulation."""

    case_id: str
    job_id: str
    drift_type: str  # "backward" or "forward"
    trajectories_geojson: dict | None = None
    source_zone_geojson: dict | None = None
    probability_contours: dict | None = None
    contour_levels: list[float] = [0.5, 0.75, 0.9]
    estimated_release_window: dict | None = None
    input_coverage_summary: dict[str, Any] = {}
    configuration: dict[str, Any] = {}
    seed: int | None = None
    execution_time_seconds: float = 0.0
    limitations: list[str] = []
    coastline_contact: list[dict] | None = None  # Forward drift only


class EnvironmentalCoverage(BaseModel):
    """Summary of environmental data coverage."""

    wind_data_available: bool = False
    current_data_available: bool = False
    wind_time_overlap: bool = False
    current_time_overlap: bool = False
    wind_geo_overlap: bool = False
    current_geo_overlap: bool = False
    warnings: list[str] = []
