"""
Oilora Blue AI — Application Configuration
All settings loaded from environment variables with sensible defaults.
"""

import logging
import os
from pathlib import Path

from pydantic_settings import BaseSettings

logger = logging.getLogger("oilora_blue.config")

# Canonical backend base directory (backend/). Relative paths — including the
# default DATABASE_PATH — resolve against this directory, never against the
# process current working directory, so the same database is used no matter
# where the server is started from.
BACKEND_BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Application
    APP_NAME: str = "Oilora Blue AI"
    APP_VERSION: str = "0.1.0"
    APP_DESCRIPTION: str = (
        "Explainable maritime oil-spill investigation and decision-support platform"
    )
    DEBUG: bool = True

    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]

    # Database
    # Single authoritative database path. The value may be relative or absolute;
    # it is resolved to an absolute path inside model_post_init. The application
    # uses Python's built-in sqlite3 module (no SQLAlchemy / aiosqlite).
    DATABASE_PATH: str = "oilora_blue.db"  # Relative to backend/ by default

    # Storage
    DATA_DIR: str = str(Path(__file__).parent.parent.parent / "data")
    CASES_DIR: str = ""  # Derived: DATA_DIR/cases
    UPLOADS_DIR: str = ""  # Derived: DATA_DIR/uploads
    OUTPUTS_DIR: str = ""  # Derived: DATA_DIR/outputs
    MODELS_DIR: str = str(Path(__file__).parent.parent.parent / "models")

    # File limits
    MAX_UPLOAD_SIZE_MB: int = 2048  # 2 GB
    ALLOWED_SAR_EXTENSIONS: list[str] = [".tif", ".tiff", ".geotiff", ".jp2"]
    ALLOWED_AIS_EXTENSIONS: list[str] = [".csv", ".parquet", ".tsv"]
    ALLOWED_ENV_EXTENSIONS: list[str] = [".nc", ".netcdf", ".nc4"]
    ALLOWED_MASK_EXTENSIONS: list[str] = [".tif", ".tiff", ".png", ".jpg", ".jpeg"]

    # Processing
    MAX_CONCURRENT_JOBS: int = 2
    TILE_SIZE: int = 512
    TILE_OVERLAP: int = 64

    # Security
    ENABLE_LOCAL_DEMO_MODE: bool = True
    LOG_LEVEL: str = "INFO"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}

    def model_post_init(self, __context, /) -> None:
        """Derive directory paths and create them if needed."""
        # Resolve the database path to an absolute path (single source of truth).
        # Relative values are anchored to the canonical backend base directory so
        # the resolved path never depends on the process current working directory.
        if not self.DATABASE_PATH:
            self.DATABASE_PATH = str(BACKEND_BASE_DIR / "oilora_blue.db")
        else:
            raw = Path(self.DATABASE_PATH).expanduser()
            if raw.is_absolute():
                resolved = raw.resolve()
            else:
                resolved = (BACKEND_BASE_DIR / raw).resolve()
            self.DATABASE_PATH = str(resolved)
        db_parent = os.path.dirname(self.DATABASE_PATH)
        if db_parent:
            try:
                os.makedirs(db_parent, exist_ok=True)
            except (OSError, FileNotFoundError):
                pass

        # Warn (never merge/delete) if a stray database exists somewhere the
        # previous CWD-relative resolution could have created it. This helps
        # catch a second database that predates the base-dir anchor.
        repo_root = BACKEND_BASE_DIR.parent
        stray_candidates = [
            Path.cwd() / "oilora_blue.db",
            repo_root / "oilora_blue.db",
        ]
        resolved_db = Path(self.DATABASE_PATH)
        for candidate in stray_candidates:
            try:
                exists = candidate.is_file() and candidate.resolve() != resolved_db
            except OSError:
                exists = False
            if exists:
                logger.warning(
                    "Stray database detected at %s — the application uses %s. "
                    "No automatic merge or deletion is performed.",
                    candidate,
                    self.DATABASE_PATH,
                )

        if not self.CASES_DIR:
            self.CASES_DIR = os.path.join(self.DATA_DIR, "cases") if self.DATA_DIR else ""
        if not self.UPLOADS_DIR:
            self.UPLOADS_DIR = os.path.join(self.DATA_DIR, "uploads") if self.DATA_DIR else ""
        if not self.OUTPUTS_DIR:
            self.OUTPUTS_DIR = os.path.join(self.DATA_DIR, "outputs") if self.DATA_DIR else ""

        # Ensure directories exist (skip when paths are empty, e.g. in tests)
        dirs = [
            d
            for d in [
                self.DATA_DIR,
                self.CASES_DIR,
                self.UPLOADS_DIR,
                self.OUTPUTS_DIR,
                self.MODELS_DIR,
            ]
            if d
        ]
        for directory in dirs:
            try:
                os.makedirs(directory, exist_ok=True)
            except (OSError, FileNotFoundError):
                pass

    @property
    def max_upload_bytes(self) -> int:
        return self.MAX_UPLOAD_SIZE_MB * 1024 * 1024


settings = Settings()
