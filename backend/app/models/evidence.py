"""
Oilora Blue AI — Evidence Models

Pydantic models for evidence manifests and investigation reports.
"""

from typing import Any

from pydantic import BaseModel


class EvidenceManifest(BaseModel):
    """Immutable evidence manifest for a case."""

    id: str
    case_id: str
    revision: int = 1
    case_metadata: dict[str, Any] = {}
    input_file_hashes: dict[str, str] = {}
    derived_artifact_hashes: dict[str, str] = {}
    data_source_provenance: list[dict[str, Any]] = []
    model_version: str = ""
    model_checksum: str = ""
    software_version: str = ""
    processing_configuration: dict[str, Any] = {}
    random_seeds: list[int] = []
    transformations: list[dict[str, Any]] = []
    analyst_review: dict[str, Any] | None = None
    candidate_score_components: list[dict[str, Any]] = []
    generation_timestamp: str = ""
    sha256_checksum: str = ""
    is_approved: bool = False
    approved_at: str | None = None


class ReportSection(BaseModel):
    """A section of the investigation report."""

    title: str
    content: str
    figures: list[dict[str, Any]] = []
    tables: list[dict[str, Any]] = []


class InvestigationReport(BaseModel):
    """Complete investigation report data."""

    case_id: str
    report_id: str
    generated_at: str
    executive_summary: str = ""
    data_sources: list[ReportSection] = []
    methods: ReportSection = ReportSection(title="Methods", content="")
    sar_image: dict | None = None
    detection_result: dict | None = None
    analyst_review: dict | None = None
    backward_drift: dict | None = None
    forward_drift: dict | None = None
    ais_quality: dict | None = None
    candidate_ranking: dict | None = None
    explainable_evidence: list[ReportSection] = []
    uncertainty_assessment: ReportSection = ReportSection(
        title="Uncertainty Assessment", content=""
    )
    limitations: ReportSection = ReportSection(title="Limitations", content="")
    manifest_checksum: str = ""
    disclaimer: str = (
        "This report supports investigation and does not establish legal guilt. "
        "All results should be verified by qualified analysts before any action is taken."
    )


class ProvenanceRecord(BaseModel):
    """Provenance record for a dataset."""

    dataset_title: str
    original_publisher: str
    official_url: str | None = None
    doi: str | None = None
    licence: str
    download_date: str
    observation_time: str | None = None
    geographic_bounds: dict | None = None
    crs: str = "EPSG:4326"
    file_format: str = ""
    original_filename: str = ""
    file_size: int = 0
    sha256_checksum: str = ""
    transformations: list[str] = []
    derived_output_relationships: list[str] = []
