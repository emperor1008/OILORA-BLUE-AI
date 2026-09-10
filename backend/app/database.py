"""
Oilora Blue AI — SQLite Database Layer

Provides synchronous SQLite database access with connection pooling.
All queries use parameterized statements to prevent SQL injection.
"""

import sqlite3
import threading
from contextlib import contextmanager

from . import config

_local = threading.local()


def get_connection() -> sqlite3.Connection:
    """Get a thread-local SQLite connection."""
    if not hasattr(_local, "connection") or _local.connection is None:
        _local.connection = sqlite3.connect(
            config.settings.DATABASE_PATH,
            timeout=30.0,
            check_same_thread=False,
        )
        _local.connection.row_factory = sqlite3.Row
        _local.connection.execute("PRAGMA journal_mode=WAL")
        _local.connection.execute("PRAGMA foreign_keys=ON")
        _local.connection.execute("PRAGMA busy_timeout=5000")
    return _local.connection


@contextmanager
def get_db():
    """Context manager for database operations."""
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def init_database():
    """Create all tables if they don't exist."""
    schema = """
    -- Cases: investigation records
    CREATE TABLE IF NOT EXISTS cases (
        id TEXT PRIMARY KEY,
        title TEXT NOT NULL,
        description TEXT DEFAULT '',
        region TEXT DEFAULT '',
        incident_time TEXT,
        observation_time TEXT,
        bbox_min_lat REAL,
        bbox_min_lon REAL,
        bbox_max_lat REAL,
        bbox_max_lon REAL,
        analyst_notes TEXT DEFAULT '',
        status TEXT DEFAULT 'created',
        current_stage TEXT DEFAULT 'registration',
        dataset_ready INTEGER DEFAULT 0,
        system_ready INTEGER DEFAULT 0,
        offline_ready INTEGER DEFAULT 0,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        completed_at TEXT
    );

    -- Files: registered data files
    CREATE TABLE IF NOT EXISTS files (
        id TEXT PRIMARY KEY,
        case_id TEXT NOT NULL,
        file_type TEXT NOT NULL CHECK(file_type IN ('sar', 'ais', 'environmental', 'mask', 'boundary', 'other')),
        original_filename TEXT NOT NULL,
        stored_filename TEXT NOT NULL,
        file_path TEXT NOT NULL,
        file_size INTEGER NOT NULL,
        mime_type TEXT,
        sha256_checksum TEXT NOT NULL,
        validation_status TEXT DEFAULT 'pending',
        validation_errors TEXT DEFAULT '[]',
        metadata TEXT DEFAULT '{}',
        created_at TEXT NOT NULL,
        FOREIGN KEY (case_id) REFERENCES cases(id) ON DELETE CASCADE
    );

    -- Jobs: background processing jobs
    CREATE TABLE IF NOT EXISTS jobs (
        id TEXT PRIMARY KEY,
        case_id TEXT NOT NULL,
        stage TEXT NOT NULL,
        status TEXT DEFAULT 'queued' CHECK(status IN (
            'queued', 'validating', 'processing',
            'awaiting_review', 'completed', 'failed', 'cancelled'
        )),
        progress REAL DEFAULT 0.0,
        configuration TEXT DEFAULT '{}',
        config_version TEXT,
        error_code TEXT,
        error_message TEXT,
        retry_count INTEGER DEFAULT 0,
        max_retries INTEGER DEFAULT 3,
        started_at TEXT,
        completed_at TEXT,
        created_at TEXT NOT NULL,
        FOREIGN KEY (case_id) REFERENCES cases(id) ON DELETE CASCADE
    );

    -- Audit log: immutable event log
    CREATE TABLE IF NOT EXISTS audit_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        case_id TEXT,
        event_type TEXT NOT NULL,
        event_data TEXT DEFAULT '{}',
        actor TEXT DEFAULT 'system',
        created_at TEXT NOT NULL
    );

    -- Evidence manifests: immutable approved evidence
    CREATE TABLE IF NOT EXISTS evidence_manifests (
        id TEXT PRIMARY KEY,
        case_id TEXT NOT NULL,
        revision INTEGER NOT NULL DEFAULT 1,
        manifest_data TEXT NOT NULL,
        sha256_checksum TEXT NOT NULL,
        is_approved INTEGER DEFAULT 0,
        approved_at TEXT,
        created_at TEXT NOT NULL,
        FOREIGN KEY (case_id) REFERENCES cases(id) ON DELETE CASCADE
    );

    -- Map viewports: last analyst viewport per case (safe display preference)
    CREATE TABLE IF NOT EXISTS map_viewports (
        case_id TEXT PRIMARY KEY,
        center_lon REAL,
        center_lat REAL,
        zoom REAL,
        bearing REAL DEFAULT 0,
        pitch REAL DEFAULT 0,
        updated_at TEXT NOT NULL,
        FOREIGN KEY (case_id) REFERENCES cases(id) ON DELETE CASCADE
    );

    -- Data sources: official provider registry. Definitions are seeded from
    -- code; state columns (configured_status, probe timestamps) persist here.
    CREATE TABLE IF NOT EXISTS data_sources (
        source_id TEXT PRIMARY KEY,
        source_name TEXT NOT NULL,
        organization TEXT NOT NULL,
        data_category TEXT NOT NULL,
        documentation_url TEXT,
        access_method TEXT NOT NULL,
        authentication_required INTEGER DEFAULT 0,
        authentication_note TEXT DEFAULT '',
        licence TEXT DEFAULT '',
        spatial_coverage TEXT DEFAULT '',
        temporal_coverage TEXT DEFAULT '',
        refresh_frequency TEXT DEFAULT '',
        expected_format TEXT DEFAULT '',
        configured_status TEXT DEFAULT 'not_configured',
        last_successful_access TEXT,
        last_failed_access TEXT,
        latest_error_category TEXT,
        last_probe_at TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );

    -- File manifests: immutable provenance record created when a file is
    -- registered. Cascades with both the case and the file record.
    CREATE TABLE IF NOT EXISTS file_manifests (
        manifest_id TEXT PRIMARY KEY,
        case_id TEXT NOT NULL,
        file_id TEXT NOT NULL,
        source_id TEXT,
        source_type TEXT,
        provider TEXT,
        product_identifier TEXT,
        acquisition_start TEXT,
        acquisition_end TEXT,
        registered_at TEXT NOT NULL,
        original_filename TEXT NOT NULL,
        stored_filename TEXT NOT NULL,
        byte_size INTEGER NOT NULL,
        sha256_checksum TEXT NOT NULL,
        media_format TEXT,
        crs TEXT,
        spatial_bounds TEXT,
        temporal_bounds TEXT,
        bands TEXT,
        validation_status TEXT NOT NULL,
        validation_messages TEXT DEFAULT '[]',
        parent_artifact TEXT,
        processing_version TEXT DEFAULT 'none',
        software_version TEXT,
        created_by TEXT DEFAULT 'system',
        created_at TEXT NOT NULL,
        FOREIGN KEY (case_id) REFERENCES cases(id) ON DELETE CASCADE,
        FOREIGN KEY (file_id) REFERENCES files(id) ON DELETE CASCADE
    );

    -- Historical incidents: source-registered reference records, kept fully
    -- separate from user-created investigations (cases). Nothing here is
    -- automatically treated as independently verified; every important field
    -- carries its own provenance via historical_incident_field_sources.
    CREATE TABLE IF NOT EXISTS historical_incidents (
        id TEXT PRIMARY KEY,
        source_id TEXT NOT NULL,
        source_record_id TEXT NOT NULL,
        canonical_name TEXT NOT NULL,
        alternative_names TEXT DEFAULT '[]',
        incident_category TEXT,
        verification_status TEXT NOT NULL DEFAULT 'source_imported',
        start_time_utc TEXT,
        end_time_utc TEXT,
        time_precision TEXT DEFAULT 'date',
        country TEXT,
        maritime_region TEXT,
        nearest_port TEXT,
        location_description TEXT,
        latitude REAL,
        longitude REAL,
        coordinate_accuracy TEXT,
        location_method TEXT,
        affected_area_geometry_geojson TEXT,
        substance_name TEXT,
        substance_category TEXT,
        quantity_min REAL,
        quantity_max REAL,
        quantity_unit TEXT,
        quantity_status TEXT,
        reported_cause TEXT,
        summary TEXT,
        response_status TEXT,
        original_payload TEXT DEFAULT '{}',
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        UNIQUE (source_id, source_record_id)
    );

    -- Sources documenting a historical incident (one per reference document).
    CREATE TABLE IF NOT EXISTS historical_incident_sources (
        id TEXT PRIMARY KEY,
        incident_id TEXT NOT NULL,
        organization TEXT NOT NULL,
        source_title TEXT,
        source_url TEXT,
        publication_date TEXT,
        accessed_at TEXT,
        source_type TEXT,
        licence_or_usage_note TEXT,
        source_quality TEXT,
        archived_reference TEXT,
        checksum TEXT,
        created_at TEXT NOT NULL,
        FOREIGN KEY (incident_id) REFERENCES historical_incidents(id) ON DELETE CASCADE
    );

    -- Field-level provenance: which source supports each normalized field.
    CREATE TABLE IF NOT EXISTS historical_incident_field_sources (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        incident_id TEXT NOT NULL,
        field_name TEXT NOT NULL,
        source_id TEXT NOT NULL,
        source_value TEXT,
        normalization_method TEXT DEFAULT 'copied',
        confidence_level TEXT DEFAULT 'high',
        curator_note TEXT,
        FOREIGN KEY (incident_id) REFERENCES historical_incidents(id) ON DELETE CASCADE,
        FOREIGN KEY (source_id) REFERENCES historical_incident_sources(id) ON DELETE CASCADE
    );

    -- Vessels mentioned in connection with an incident (never "guilty").
    CREATE TABLE IF NOT EXISTS historical_incident_vessels (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        incident_id TEXT NOT NULL,
        vessel_name TEXT,
        vessel_type TEXT,
        imo TEXT,
        mmsi TEXT,
        relationship_type TEXT,
        attribution_status TEXT NOT NULL DEFAULT 'mentioned',
        source_id TEXT NOT NULL,
        FOREIGN KEY (incident_id) REFERENCES historical_incidents(id) ON DELETE CASCADE,
        FOREIGN KEY (source_id) REFERENCES historical_incident_sources(id) ON DELETE CASCADE
    );

    -- Sourced environmental-impact statements.
    CREATE TABLE IF NOT EXISTS historical_incident_impacts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        incident_id TEXT NOT NULL,
        impact_type TEXT,
        description TEXT,
        measured_value REAL,
        unit TEXT,
        estimate_status TEXT,
        source_id TEXT NOT NULL,
        FOREIGN KEY (incident_id) REFERENCES historical_incidents(id) ON DELETE CASCADE,
        FOREIGN KEY (source_id) REFERENCES historical_incident_sources(id) ON DELETE CASCADE
    );

    -- Sourced response/cleanup actions.
    CREATE TABLE IF NOT EXISTS historical_incident_responses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        incident_id TEXT NOT NULL,
        organization TEXT,
        action_type TEXT,
        description TEXT,
        action_time TEXT,
        source_id TEXT NOT NULL,
        FOREIGN KEY (incident_id) REFERENCES historical_incidents(id) ON DELETE CASCADE,
        FOREIGN KEY (source_id) REFERENCES historical_incident_sources(id) ON DELETE CASCADE
    );

    -- Satellite catalogue matches: metadata-level observations of an incident
    -- area by a satellite. Confirms the area was observed — never that oil is
    -- visible or that any product was downloaded.
    CREATE TABLE IF NOT EXISTS satellite_catalog_matches (
        id TEXT PRIMARY KEY,
        historical_incident_id TEXT NOT NULL,
        provider TEXT NOT NULL,
        collection TEXT NOT NULL,
        item_id TEXT NOT NULL,
        product_identifier TEXT,
        platform TEXT,
        acquisition_start TEXT,
        acquisition_end TEXT,
        acquisition_mode TEXT,
        processing_level TEXT,
        polarizations TEXT DEFAULT '[]',
        orbit_direction TEXT,
        geometry_geojson TEXT,
        bbox TEXT,
        metadata_url TEXT,
        asset_access_status TEXT DEFAULT 'metadata_only',
        temporal_distance_hours REAL,
        spatial_overlap_ratio REAL,
        catalogue_checked_at TEXT NOT NULL,
        UNIQUE (historical_incident_id, item_id),
        FOREIGN KEY (historical_incident_id) REFERENCES historical_incidents(id) ON DELETE CASCADE
    );

    -- Registered SAR assets tied to an incident (optionally through a case).
    CREATE TABLE IF NOT EXISTS incident_satellite_assets (
        id TEXT PRIMARY KEY,
        historical_incident_id TEXT NOT NULL,
        case_id TEXT,
        satellite_catalog_match_id TEXT,
        registered_file_id TEXT,
        asset_type TEXT NOT NULL,
        original_or_derived TEXT NOT NULL,
        processing_status TEXT NOT NULL DEFAULT 'uploaded',
        provenance_status TEXT NOT NULL DEFAULT 'pending',
        preview_status TEXT NOT NULL DEFAULT 'missing',
        checksum_sha256 TEXT,
        created_at TEXT NOT NULL,
        FOREIGN KEY (historical_incident_id) REFERENCES historical_incidents(id) ON DELETE CASCADE,
        FOREIGN KEY (case_id) REFERENCES cases(id) ON DELETE SET NULL,
        FOREIGN KEY (satellite_catalog_match_id) REFERENCES satellite_catalog_matches(id) ON DELETE SET NULL,
        FOREIGN KEY (registered_file_id) REFERENCES files(id) ON DELETE SET NULL
    );

    -- Import runs: repeatable, auditable source ingestion metadata.
    CREATE TABLE IF NOT EXISTS historical_incident_import_runs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        source_name TEXT NOT NULL,
        source_url TEXT,
        source_version_or_retrieval_date TEXT,
        started_at TEXT NOT NULL,
        completed_at TEXT,
        records_received INTEGER DEFAULT 0,
        records_created INTEGER DEFAULT 0,
        records_updated INTEGER DEFAULT 0,
        records_rejected INTEGER DEFAULT 0,
        rejection_report TEXT DEFAULT '[]',
        source_checksum TEXT,
        import_status TEXT NOT NULL DEFAULT 'running'
    );

    -- Indexes for performance
    CREATE INDEX IF NOT EXISTS idx_files_case_id ON files(case_id);
    CREATE INDEX IF NOT EXISTS idx_files_file_type ON files(file_type);
    CREATE INDEX IF NOT EXISTS idx_jobs_case_id ON jobs(case_id);
    CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
    CREATE INDEX IF NOT EXISTS idx_audit_log_case_id ON audit_log(case_id);
    CREATE INDEX IF NOT EXISTS idx_evidence_case_id ON evidence_manifests(case_id);
    CREATE INDEX IF NOT EXISTS idx_manifests_case_id ON file_manifests(case_id);
    CREATE INDEX IF NOT EXISTS idx_manifests_file_id ON file_manifests(file_id);

    -- Historical-incident indexes
    CREATE INDEX IF NOT EXISTS idx_hist_source_record ON historical_incidents(source_id, source_record_id);
    CREATE INDEX IF NOT EXISTS idx_hist_start_time ON historical_incidents(start_time_utc);
    CREATE INDEX IF NOT EXISTS idx_hist_country ON historical_incidents(country);
    CREATE INDEX IF NOT EXISTS idx_hist_category ON historical_incidents(incident_category);
    CREATE INDEX IF NOT EXISTS idx_hist_verification ON historical_incidents(verification_status);
    CREATE INDEX IF NOT EXISTS idx_hist_coords ON historical_incidents(latitude, longitude);
    CREATE INDEX IF NOT EXISTS idx_hist_sources_incident ON historical_incident_sources(incident_id);
    CREATE INDEX IF NOT EXISTS idx_hist_field_incident ON historical_incident_field_sources(incident_id);
    CREATE UNIQUE INDEX IF NOT EXISTS idx_hist_field_uniq ON
        historical_incident_field_sources(incident_id, source_id, field_name);
    CREATE INDEX IF NOT EXISTS idx_hist_matches_incident ON satellite_catalog_matches(historical_incident_id);
    CREATE INDEX IF NOT EXISTS idx_hist_assets_incident ON incident_satellite_assets(historical_incident_id);
    """

    with get_db() as conn:
        conn.executescript(schema)

    _ensure_cases_historical_column()

    # Seed the provider registry (definitions from code, state preserved).
    from .services.source_registry import seed_source_registry

    seed_source_registry()

    with get_db() as conn:
        conn.executescript(schema)


def _ensure_cases_historical_column() -> None:
    """Idempotently add cases.historical_incident_id (non-destructive).

    Newer schema versions link an investigation back to the historical
    reference record it was created from. CREATE TABLE IF NOT EXISTS cannot add
    a column to an existing table, so this runs a guarded ALTER TABLE when the
    column is absent. Existing rows are untouched.
    """
    with get_db() as conn:
        columns = [row["name"] for row in conn.execute("PRAGMA table_info(cases)").fetchall()]
        if "historical_incident_id" not in columns:
            conn.execute("ALTER TABLE cases ADD COLUMN historical_incident_id TEXT")
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_cases_historical_incident "
                "ON cases(historical_incident_id)"
            )


def close_database():
    """Close the thread-local database connection."""
    if hasattr(_local, "connection") and _local.connection is not None:
        _local.connection.close()
        _local.connection = None
