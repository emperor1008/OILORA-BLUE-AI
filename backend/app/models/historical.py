"""
Oilora Blue AI — Historical Incident Models

Typed request/response bodies for the historical-incident explorer. Responses
use the project's envelope pattern with typed payloads built by the service so
list payloads stay compact.
"""

from typing import Any

from pydantic import BaseModel, Field

from .common import BaseResponse


class CreateInvestigationRequest(BaseModel):
    """User-confirmed creation of a working case from a historical incident.

    Only source-supported fields are copied; everything else stays empty.
    """

    analyst_notes: str = Field(default="", max_length=5000)
    confirm: bool = True


class SatelliteSearchRequest(BaseModel):
    """Parameters for a Sentinel-1 catalogue metadata search."""

    window_days: int = Field(default=3, ge=1, le=30)
    acquisition_mode: str = Field(default="IW", max_length=20)
    processing_level: str = Field(default="GRD", max_length=20)
    polarization: str | None = Field(default=None, max_length=20)
    limit: int = Field(default=20, ge=1, le=50)


class PaginatedIncidentResponse(BaseResponse):
    """Compact incident list with pagination metadata."""

    total: int = 0
    limit: int = 25
    offset: int = 0
    next_cursor: str | None = None
    data: Any = None
