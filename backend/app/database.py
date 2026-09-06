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

    -- Indexes for performance
    CREATE INDEX IF NOT EXISTS idx_files_case_id ON files(case_id);
    CREATE INDEX IF NOT EXISTS idx_files_file_type ON files(file_type);
    CREATE INDEX IF NOT EXISTS idx_jobs_case_id ON jobs(case_id);
    CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
    CREATE INDEX IF NOT EXISTS idx_audit_log_case_id ON audit_log(case_id);
    CREATE INDEX IF NOT EXISTS idx_evidence_case_id ON evidence_manifests(case_id);
    """

    with get_db() as conn:
        conn.executescript(schema)


def close_database():
    """Close the thread-local database connection."""
    if hasattr(_local, "connection") and _local.connection is not None:
        _local.connection.close()
        _local.connection = None
