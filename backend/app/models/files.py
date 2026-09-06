"""
Oilora Blue AI — File Models

Pydantic models for file registration and validation.
"""

from typing import Any

from pydantic import BaseModel, Field


class FileRegistration(BaseModel):
    """Metadata for a file registration request."""

    file_type: str = Field(..., description="sar|ais|environmental|mask|boundary|other")
    description: str = Field(default="", max_length=500)


class FileValidationResult(BaseModel):
    """Result of file validation."""

    valid: bool
    errors: list[str] = []
    warnings: list[str] = []
    metadata: dict[str, Any] = {}


class FileInfo(BaseModel):
    """Stored file information."""

    id: str
    case_id: str
    file_type: str
    original_filename: str
    stored_filename: str
    file_size: int
    mime_type: str | None
    sha256_checksum: str
    validation_status: str
    validation_errors: list[str] = []
    metadata: dict[str, Any] = {}
    created_at: str


class SARMetadata(BaseModel):
    """SAR raster metadata extracted during validation."""

    width: int = 0
    height: int = 0
    bands: int = 0
    crs: str | None = None
    pixel_size_x: float = 0.0
    pixel_size_y: float = 0.0
    bounds: dict | None = None
    nodata: float | None = None
    dtype: str | None = None
    acquisition_time: str | None = None
    polarisation: str | None = None
    satellite: str | None = None


class AISMetadata(BaseModel):
    """AIS data metadata extracted during validation."""

    record_count: int = 0
    columns_found: list[str] = []
    column_mapping: dict[str, str] = {}
    time_range: dict | None = None
    geographic_bounds: dict | None = None
    missing_values: dict[str, int] = {}
    warnings: list[str] = []


class EnvironmentalMetadata(BaseModel):
    """Environmental NetCDF metadata."""

    variables_found: list[str] = []
    required_variables: list[str] = []
    missing_variables: list[str] = []
    units: dict[str, str] = {}
    time_range: dict | None = None
    geographic_bounds: dict | None = None
    spatial_resolution: dict | None = None
