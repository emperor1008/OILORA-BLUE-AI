"""
Oilora Blue AI — Case Models

Pydantic models for case management API contracts.
"""

from pydantic import BaseModel, Field


class CaseCreate(BaseModel):
    """Request model for creating a new investigation case."""

    title: str = Field(..., min_length=1, max_length=200, description="Case title")
    description: str = Field(default="", max_length=2000, description="Case description")
    region: str = Field(default="", max_length=200, description="Geographic region")
    incident_time: str | None = Field(None, description="ISO 8601 incident time")
    observation_time: str | None = Field(None, description="ISO 8601 observation time")
    bbox_min_lat: float | None = Field(None, ge=-90, le=90)
    bbox_min_lon: float | None = Field(None, ge=-180, le=180)
    bbox_max_lat: float | None = Field(None, ge=-90, le=90)
    bbox_max_lon: float | None = Field(None, ge=-180, le=180)
    analyst_notes: str = Field(default="", max_length=5000, description="Analyst notes")


class CaseUpdate(BaseModel):
    """Request model for updating a case."""

    title: str | None = Field(None, min_length=1, max_length=200)
    description: str | None = Field(None, max_length=2000)
    region: str | None = Field(None, max_length=200)
    incident_time: str | None = None
    observation_time: str | None = None
    bbox_min_lat: float | None = Field(None, ge=-90, le=90)
    bbox_min_lon: float | None = Field(None, ge=-180, le=180)
    bbox_max_lat: float | None = Field(None, ge=-90, le=90)
    bbox_max_lon: float | None = Field(None, ge=-180, le=180)
    analyst_notes: str | None = Field(None, max_length=5000)


class CaseSummary(BaseModel):
    """Compact case information for list views."""

    id: str
    title: str
    description: str
    region: str
    status: str
    current_stage: str
    dataset_ready: bool
    system_ready: bool
    offline_ready: bool
    created_at: str
    updated_at: str
    file_count: int = 0


class CaseDetail(BaseModel):
    """Full case information for detail views."""

    id: str
    title: str
    description: str
    region: str
    incident_time: str | None
    observation_time: str | None
    bbox_min_lat: float | None
    bbox_min_lon: float | None
    bbox_max_lat: float | None
    bbox_max_lon: float | None
    analyst_notes: str
    status: str
    current_stage: str
    dataset_ready: bool
    system_ready: bool
    offline_ready: bool
    created_at: str
    updated_at: str
    completed_at: str | None
    files: list = []
    jobs: list = []
