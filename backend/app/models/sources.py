"""
Oilora Blue AI — Data Source & Manifest Models

Pydantic models for the provider registry and per-file provenance manifests.
Credential values never appear in any of these models — only the masked
``authentication_configured`` boolean is exposed.
"""

from typing import Any

from pydantic import BaseModel, Field


class SourceInfo(BaseModel):
    """Safe public record for one registered data source."""

    source_id: str
    source_name: str
    organization: str
    data_category: str
    documentation_url: str = ""
    access_method: str = ""
    authentication_required: bool = False
    authentication_configured: bool = False
    authentication_note: str = ""
    licence: str = ""
    spatial_coverage: str = ""
    temporal_coverage: str = ""
    refresh_frequency: str = ""
    expected_format: str = ""
    configured_status: str = "not_configured"
    latest_error_category: str = "none"
    last_successful_access: str | None = None
    last_failed_access: str | None = None
    last_probe_at: str | None = None


class FileManifest(BaseModel):
    """Provenance manifest for one registered file."""

    manifest_id: str
    case_id: str
    file_id: str
    source_id: str | None = None
    source_type: str | None = None
    provider: str | None = None
    product_identifier: str | None = None
    acquisition_start: str | None = None
    acquisition_end: str | None = None
    registered_at: str
    original_filename: str
    stored_filename: str
    byte_size: int
    sha256_checksum: str
    media_format: str | None = None
    crs: str | None = None
    spatial_bounds: dict[str, Any] | None = None
    temporal_bounds: dict[str, Any] | None = None
    bands: list[Any] | None = None
    validation_status: str = "format_checked"
    validation_messages: list[str] = Field(default_factory=list)
    parent_artifact: str | None = None
    processing_version: str = "none"
    software_version: str | None = None
    created_by: str = "system"
    created_at: str
