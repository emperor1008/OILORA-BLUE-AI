"""
Oilora Blue AI — Candidate Models

Pydantic models for vessel candidate filtering and scoring.
"""

from typing import Any

from pydantic import BaseModel, Field


class CandidateFilterConfig(BaseModel):
    """Configuration for candidate filtering."""

    source_proximity_km: float = Field(default=50.0, gt=0)
    time_window_hours: float = Field(default=24.0, gt=0)
    trajectory_proximity_km: float = Field(default=20.0, gt=0)
    min_data_quality: float = Field(default=0.3, ge=0.0, le=1.0)
    max_speed_knots: float = Field(default=25.0, gt=0)


class CandidateScoreComponents(BaseModel):
    """Individual scoring components for a candidate vessel."""

    source_proximity: float = Field(default=0.0, ge=0.0, le=1.0)
    temporal_alignment: float = Field(default=0.0, ge=0.0, le=1.0)
    trajectory_compatibility: float = Field(default=0.0, ge=0.0, le=1.0)
    ais_data_quality: float = Field(default=0.0, ge=0.0, le=1.0)
    ais_gap_evidence: float = Field(default=0.0, ge=0.0, le=1.0)
    motion_anomaly: float = Field(default=0.0, ge=0.0, le=1.0)
    vessel_context: float = Field(default=0.0, ge=0.0, le=1.0)


class CandidateScoreWeights(BaseModel):
    """Weights for scoring components (must sum to 1.0)."""

    source_proximity: float = 0.25
    temporal_alignment: float = 0.20
    trajectory_compatibility: float = 0.20
    ais_data_quality: float = 0.10
    ais_gap_evidence: float = 0.10
    motion_anomaly: float = 0.10
    vessel_context: float = 0.05


class VesselCandidate(BaseModel):
    """A scored vessel candidate."""

    mmsi: str
    vessel_name: str | None = None
    vessel_type: str | None = None
    overall_score: float = Field(ge=0.0, le=1.0)
    components: CandidateScoreComponents
    supporting_evidence: list[str] = []
    reducing_evidence: list[str] = []
    data_limitations: list[str] = []
    exclusion_reason: str | None = None
    trajectory_geojson: dict | None = None
    nearest_approach_km: float | None = None
    time_in_region_hours: float | None = None


class CandidateRanking(BaseModel):
    """Complete candidate ranking results for a case."""

    case_id: str
    job_id: str
    candidates: list[VesselCandidate] = []
    total_vessels_analyzed: int = 0
    vessels_in_filter: int = 0
    scoring_weights: CandidateScoreWeights = CandidateScoreWeights()
    configuration: dict[str, Any] = {}
    ambiguities: list[str] = []
    execution_time_seconds: float = 0.0
