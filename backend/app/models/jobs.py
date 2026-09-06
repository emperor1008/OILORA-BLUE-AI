"""
Oilora Blue AI — Job Models

Pydantic models for background job tracking.
"""

from typing import Any

from pydantic import BaseModel, Field


class JobCreate(BaseModel):
    """Request to create a new processing job."""

    case_id: str
    stage: str
    configuration: dict[str, Any] = {}
    config_version: str | None = None


class JobUpdate(BaseModel):
    """Internal job status update."""

    status: str | None = None
    progress: float | None = Field(None, ge=0.0, le=1.0)
    error_code: str | None = None
    error_message: str | None = None


class JobInfo(BaseModel):
    """Job information for API responses."""

    id: str
    case_id: str
    stage: str
    status: str
    progress: float
    error_code: str | None = None
    error_message: str | None = None
    retry_count: int
    max_retries: int
    started_at: str | None = None
    completed_at: str | None = None
    created_at: str
