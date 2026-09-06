"""
Oilora Blue AI — AIS Models

Pydantic models for AIS data ingestion, trajectory reconstruction, and quality reporting.
"""

from pydantic import BaseModel


class AISColumnMapping(BaseModel):
    """Column mapping for AIS data files."""

    mmsi: str = "MMSI"
    timestamp: str = "BaseDateTime"
    latitude: str = "LAT"
    longitude: str = "LON"
    speed: str = "SOG"
    course: str = "COG"
    heading: str = "Heading"
    vessel_type: str = "VesselType"
    vessel_name: str = "VesselName"


class AISQualityReport(BaseModel):
    """Quality report for ingested AIS data."""

    total_records: int = 0
    valid_records: int = 0
    duplicate_records: int = 0
    invalid_positions: int = 0
    impossible_jumps: int = 0
    missing_values: dict[str, int] = {}
    time_gaps: list[dict] = []
    unique_vessels: int = 0
    time_range: dict | None = None
    geographic_bounds: dict | None = None
    warnings: list[str] = []
    errors: list[str] = []


class VesselTrajectory(BaseModel):
    """Reconstructed trajectory for a single vessel."""

    mmsi: str
    vessel_name: str | None = None
    vessel_type: str | None = None
    trajectory_geojson: dict | None = None
    raw_positions_count: int = 0
    interpolated_count: int = 0
    gap_segments: list[dict] = []
    quality_score: float = 0.0
    time_range: dict | None = None
    geographic_bounds: dict | None = None
    warnings: list[str] = []
