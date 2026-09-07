"""
Oilora Blue AI — Interactive Map Models

Pydantic contracts for the maritime intelligence map API.

Layer state semantics (typed distinction between honest states):

- ready             — genuine data exists and can be rendered
- not_processed     — the scientific stage that produces this layer has not run
- missing_input     — the required registered input for the stage does not exist
- failed            — the stage ran and failed (or its input is corrupt)
- coverage_mismatch — sources exist but do not overlap geographically/temporally
- empty             — a valid stage completed with no qualifying output
- unavailable       — support/configuration is absent (library, source, dataset)
- processing        — a job is currently running
- awaiting_review   — output exists and waits for analyst review
"""

from typing import Any, Literal

from pydantic import BaseModel, Field

LayerState = Literal[
    "ready",
    "not_processed",
    "missing_input",
    "failed",
    "coverage_mismatch",
    "empty",
    "unavailable",
    "processing",
    "awaiting_review",
]


class MapBounds(BaseModel):
    """Geographic bounding box in WGS 84 (decimal degrees)."""

    min_lat: float = Field(..., ge=-90, le=90)
    min_lon: float = Field(..., ge=-180, le=180)
    max_lat: float = Field(..., ge=-90, le=90)
    max_lon: float = Field(..., ge=-180, le=180)


class MapLegendItem(BaseModel):
    """One legend entry for a map layer."""

    label: str
    color: str
    fill: str | None = None
    dash: list[float] | None = None
    width: float | None = None
    symbol: str | None = None


class MapLegend(BaseModel):
    """Legend configuration for a map layer."""

    title: str = ""
    items: list[MapLegendItem] = Field(default_factory=list)


class MapLayerInfo(BaseModel):
    """Metadata describing one map layer."""

    id: str
    name: str
    category: str
    kind: str = "vector"  # vector | raster
    state: LayerState = "unavailable"
    reason: str = ""
    selectable: bool = False
    timeline: bool = False
    exportable: bool = False
    opacity_default: float = 1.0
    min_zoom: float = 0.0
    crs: str = "EPSG:4326"
    timestamps: dict[str, str] | None = None
    legend: MapLegend = Field(default_factory=MapLegend)


class ViewportState(BaseModel):
    """Analyst map viewport (safe display preference, no scientific data)."""

    center_lon: float = Field(..., ge=-180, le=180)
    center_lat: float = Field(..., ge=-90, le=90)
    zoom: float = Field(..., ge=0, le=24)
    bearing: float = Field(0, ge=-180, le=180)
    pitch: float = Field(0, ge=0, le=85)


class GeoValidationResult(BaseModel):
    """Result of validating a GeoJSON feature collection."""

    valid: bool
    errors: list[str] = Field(default_factory=list)
    normalized: dict[str, Any] | None = None
