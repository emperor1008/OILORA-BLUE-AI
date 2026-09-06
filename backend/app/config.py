"""
Oilora Blue AI — Application Configuration
All settings loaded from environment variables with sensible defaults.
"""

import os
from pathlib import Path

from pydantic_settings import BaseSettings


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
        if not self.DATABASE_PATH:
            self.DATABASE_PATH = str(Path(__file__).parent.parent / "oilora_blue.db")
        else:
            self.DATABASE_PATH = str(Path(self.DATABASE_PATH).expanduser().resolve())
        db_parent = os.path.dirname(self.DATABASE_PATH)
        if db_parent:
            try:
                os.makedirs(db_parent, exist_ok=True)
            except (OSError, FileNotFoundError):
                pass

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
