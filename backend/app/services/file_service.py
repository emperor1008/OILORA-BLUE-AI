"""
Oilora Blue AI — File Validation & Upload Service

Handles secure file upload, validation, checksum generation, and storage.
Implements all security requirements from Document 03.
"""

import hashlib
import json
import os
import re
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .. import config
from ..database import get_db

# Magic byte signatures for file type verification
MAGIC_SIGNATURES = {
    "geotiff": [b"II\x2a\x00", b"MM\x00\x2a", b"II\x2a\x00\x10"],  # TIFF LE, TIFF BE
    "jp2": [b"\x00\x00\x00\x0c\x6a\x50\x20\x20"],
    "csv": None,  # Text files checked differently
    "netcdf": [b"\x89\x48\x44\x46"],  # HDF5/NetCDF4 header
    "parquet": [b"PAR1"],
    "png": [b"\x89PNG\r\n\x1a\n"],
    "jpeg": [b"\xff\xd8\xff"],
}

# Dangerous executable signatures
DANGEROUS_SIGNATURES = [
    b"MZ",  # Windows PE
    b"\x7fELF",  # Linux ELF
    b"\xca\xfe\xba\xbe",  # Mach-O
    b"PK\x03\x04",  # ZIP (could be malicious archive)
]


class FileService:
    """Service for secure file handling."""

    @staticmethod
    def generate_id() -> str:
        return f"file-{uuid.uuid4().hex[:12]}"

    @staticmethod
    def now_iso() -> str:
        return datetime.now(UTC).isoformat()

    @classmethod
    def compute_sha256(cls, file_path: str, chunk_size: int = 8192) -> str:
        """Compute SHA-256 checksum using streamed processing."""
        sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            while True:
                chunk = f.read(chunk_size)
                if not chunk:
                    break
                sha256.update(chunk)
        return sha256.hexdigest()

    @classmethod
    def sanitize_filename(cls, filename: str) -> str:
        """Sanitize filename to prevent path traversal and other attacks."""
        # Remove path components
        filename = os.path.basename(filename)
        # Remove null bytes
        filename = filename.replace("\x00", "")
        # Remove dangerous characters
        filename = re.sub(r'[<>:"/\\|?*]', "_", filename)
        # Remove leading/trailing spaces and dots
        filename = filename.strip(" .")
        # Limit length
        if len(filename) > 255:
            name, ext = os.path.splitext(filename)
            filename = name[: 255 - len(ext)] + ext
        # Fallback if empty
        if not filename:
            filename = "unnamed_file"
        return filename

    @classmethod
    def validate_path_safety(cls, file_path: str, allowed_root: str) -> bool:
        """Ensure the file path stays within the allowed directory."""
        try:
            resolved = Path(file_path).resolve()
            allowed = Path(allowed_root).resolve()
            return str(resolved).startswith(str(allowed))
        except (ValueError, OSError):
            return False

    @classmethod
    def check_magic_bytes(cls, file_path: str, expected_type: str) -> tuple[bool, str]:
        """Verify file signature matches expected type."""
        try:
            with open(file_path, "rb") as f:
                header = f.read(16)
        except OSError:
            return False, "Cannot read file header"

        # Check for dangerous signatures first
        for sig in DANGEROUS_SIGNATURES:
            if header.startswith(sig):
                return False, f"File contains executable signature: {sig!r}"

        # Check expected type
        if expected_type == "sar":
            # Sentinel-1 SAR scenes are expected as GeoTIFF/COG or JP2
            if header[:4] in (b"II\x2a\x00", b"MM\x00\x2a"):
                return True, "Valid TIFF signature"
            if header[:8] == b"\x00\x00\x00\x0c\x6a\x50\x20\x20":
                return True, "Valid JP2 signature"
            return False, f"Expected TIFF/GeoTIFF signature, got: {header[:4].hex()}"

        elif expected_type == "mask":
            # Ground-truth masks may be georeferenced TIFF or plain PNG/JPEG
            if header[:4] in (b"II\x2a\x00", b"MM\x00\x2a"):
                return True, "Valid TIFF signature"
            if header[:4] == b"\x89PNG":
                return True, "Valid PNG signature"
            if header[:3] == b"\xff\xd8\xff":
                return True, "Valid JPEG signature"
            return False, f"Expected TIFF/PNG/JPEG signature, got: {header[:4].hex()}"

        elif expected_type == "environmental":
            if header[:4] == b"\x89\x48\x44\x46":
                return True, "Valid NetCDF4/HDF5 signature"
            return False, f"Expected NetCDF signature, got: {header[:4].hex()}"

        elif expected_type == "ais":
            if header[:4] == b"PAR1":
                return True, "Valid Parquet signature"
            # CSV: check if text
            try:
                header.decode("utf-8", errors="strict")
                return True, "Text file (CSV/TSV)"
            except UnicodeDecodeError:
                return False, "Not a valid text file for AIS data"

        return True, "Signature check skipped for unknown type"

    @classmethod
    def validate_file_extension(cls, filename: str, file_type: str) -> tuple[bool, str]:
        """Validate file extension against allowed types."""
        ext = Path(filename).suffix.lower()
        allowed = {
            "sar": config.settings.ALLOWED_SAR_EXTENSIONS,
            "ais": config.settings.ALLOWED_AIS_EXTENSIONS,
            "environmental": config.settings.ALLOWED_ENV_EXTENSIONS,
            "mask": config.settings.ALLOWED_MASK_EXTENSIONS,
            "boundary": [".geojson", ".json", ".shp"],
            "other": [".csv", ".json", ".geojson", ".txt"],
        }
        if ext in allowed.get(file_type, []):
            return True, f"Valid extension: {ext}"
        return (
            False,
            f"Invalid extension '{ext}' for {file_type} files. Allowed: {allowed.get(file_type, [])}",
        )

    @classmethod
    def validate_file_size(cls, file_path: str) -> tuple[bool, str]:
        """Check file size against limits."""
        size = os.path.getsize(file_path)
        if size == 0:
            return False, "File is empty"
        if size > config.settings.max_upload_bytes:
            max_mb = config.settings.MAX_UPLOAD_SIZE_MB
            actual_mb = size / (1024 * 1024)
            return False, f"File too large: {actual_mb:.1f} MB exceeds {max_mb} MB limit"
        return True, f"File size OK: {size / (1024 * 1024):.1f} MB"

    @classmethod
    def get_mime_type(cls, filename: str) -> str:
        """Determine MIME type from extension."""
        ext = Path(filename).suffix.lower()
        mime_map = {
            ".tif": "image/tiff",
            ".tiff": "image/tiff",
            ".geotiff": "image/tiff",
            ".jp2": "image/jp2",
            ".csv": "text/csv",
            ".tsv": "text/tab-separated-values",
            ".parquet": "application/octet-stream",
            ".nc": "application/x-netcdf",
            ".netcdf": "application/x-netcdf",
            ".nc4": "application/x-netcdf",
            ".geojson": "application/geo+json",
            ".json": "application/json",
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".shp": "application/octet-stream",
        }
        return mime_map.get(ext, "application/octet-stream")

    @classmethod
    def validate_upload(cls, file_path: str, filename: str, file_type: str) -> dict[str, Any]:
        """
        Run all security and format validations on an uploaded file.
        Returns a validation result dict.
        """
        errors = []
        warnings = []
        metadata: dict[str, Any] = {}

        # 1. Sanitize filename
        safe_name = cls.sanitize_filename(filename)
        if safe_name != filename:
            warnings.append(f"Filename was sanitized: '{filename}' → '{safe_name}'")

        # 2. Validate extension
        ext_ok, ext_msg = cls.validate_file_extension(safe_name, file_type)
        if not ext_ok:
            errors.append(ext_msg)

        # 3. Validate file size
        size_ok, size_msg = cls.validate_file_size(file_path)
        if not size_ok:
            errors.append(size_msg)

        # 4. Validate path safety
        data_root = config.settings.DATA_DIR
        if not cls.validate_path_safety(file_path, data_root):
            errors.append("Path traversal detected: file path escapes allowed directory")

        # 5. Check magic bytes
        magic_ok, magic_msg = cls.check_magic_bytes(file_path, file_type)
        if not magic_ok:
            errors.append(magic_msg)

        # 6. Compute checksum
        try:
            checksum = cls.compute_sha256(file_path)
            metadata["sha256"] = checksum
        except OSError as e:
            errors.append(f"Cannot compute checksum: {e}")

        # 7. Store MIME type
        metadata["mime_type"] = cls.get_mime_type(safe_name)
        metadata["original_filename"] = filename
        metadata["sanitized_filename"] = safe_name
        metadata["file_size"] = os.path.getsize(file_path) if os.path.exists(file_path) else 0
        metadata["extension"] = Path(safe_name).suffix.lower()

        valid = len(errors) == 0

        return {
            "valid": valid,
            "errors": errors,
            "warnings": warnings,
            "metadata": metadata,
        }

    @classmethod
    def register_file(
        cls,
        case_id: str,
        file_path: str,
        original_filename: str,
        file_type: str,
        extra_metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        """Register a validated file in the database.

        ``extra_metadata`` (e.g. Sentinel-1 provenance supplied by the analyst)
        is merged into the stored metadata for later scientific stages. Only
        whitelisted keys should be passed by the router.
        """
        # Run validation first
        validation = cls.validate_upload(file_path, original_filename, file_type)
        if not validation["valid"]:
            return None

        file_id = cls.generate_id()
        now = cls.now_iso()
        meta = validation["metadata"]
        if extra_metadata:
            meta.update(extra_metadata)
        safe_name = meta["sanitized_filename"]

        # Generate stored filename
        stored_filename = f"{file_id}_{safe_name}"
        stored_path = os.path.join(config.settings.UPLOADS_DIR, case_id, stored_filename)
        os.makedirs(os.path.dirname(stored_path), exist_ok=True)

        # Move file to storage
        if file_path != stored_path:
            import shutil

            shutil.move(file_path, stored_path)

        with get_db() as conn:
            conn.execute(
                """INSERT INTO files (
                    id, case_id, file_type, original_filename, stored_filename,
                    file_path, file_size, mime_type, sha256_checksum,
                    validation_status, validation_errors, metadata, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    file_id,
                    case_id,
                    file_type,
                    original_filename,
                    stored_filename,
                    stored_path,
                    meta["file_size"],
                    meta["mime_type"],
                    meta["sha256"],
                    "validated" if validation["valid"] else "failed",
                    json.dumps(validation["errors"]),
                    json.dumps(meta),
                    now,
                ),
            )

            # Audit event
            conn.execute(
                """INSERT INTO audit_log (case_id, event_type, event_data, created_at)
                   VALUES (?, ?, ?, ?)""",
                (
                    case_id,
                    "file_registered",
                    json.dumps(
                        {
                            "file_id": file_id,
                            "file_type": file_type,
                            "filename": original_filename,
                            "sha256": meta["sha256"],
                        }
                    ),
                    now,
                ),
            )

            # Update case dataset readiness
            registered_types = conn.execute(
                "SELECT DISTINCT file_type FROM files WHERE case_id = ? AND validation_status = 'validated'",
                (case_id,),
            ).fetchall()
            types_set = {r[0] for r in registered_types}
            # Case is data-ready if it has at least SAR data
            dataset_ready = 1 if "sar" in types_set else 0
            conn.execute(
                "UPDATE cases SET dataset_ready = ?, updated_at = ? WHERE id = ?",
                (dataset_ready, now, case_id),
            )

        return cls.to_public_dict(
            {
                "id": file_id,
                "case_id": case_id,
                "file_type": file_type,
                "original_filename": original_filename,
                "stored_filename": stored_filename,
                "file_path": stored_path,  # stripped by to_public_dict
                "file_size": meta["file_size"],
                "mime_type": meta["mime_type"],
                "sha256_checksum": meta["sha256"],
                "validation_status": "validated",
                "validation_errors": validation["errors"],
                "metadata": meta,
                "created_at": now,
            }
        )

    @staticmethod
    def validate_sar_provenance(
        product_identifier: str | None,
        acquisition_time: str | None,
        provenance_source: str | None,
        polarization: str | None,
    ) -> list[str]:
        """Validate optional Sentinel-1 provenance fields; returns error list."""
        from ..validation import normalize_iso_utc

        errors = []
        for label, value, limit in [
            ("product_identifier", product_identifier, 200),
            ("provenance_source", provenance_source, 500),
            ("polarization", polarization, 20),
        ]:
            if value is not None and len(value) > limit:
                errors.append(f"{label} exceeds {limit} characters")
        if acquisition_time:
            try:
                normalize_iso_utc(acquisition_time)
            except ValueError as exc:
                errors.append(f"acquisition_time {exc}")
        return errors

    @staticmethod
    def to_public_dict(file_row: dict[str, Any]) -> dict[str, Any]:
        """
        Convert a stored file record into a safe public response dict.

        The absolute operating-system file path is never exposed. Only safe
        identifiers and metadata are returned; `download_available` is an
        explicit, honest flag (no download endpoint exists yet).
        """
        public = {k: v for k, v in file_row.items() if k not in ("file_path",) and v is not None}
        public["download_available"] = False
        return public

    @classmethod
    def get_case_files(cls, case_id: str) -> list[dict[str, Any]]:
        """Get all files for a case (safe public records)."""
        with get_db() as conn:
            rows = conn.execute(
                "SELECT * FROM files WHERE case_id = ? ORDER BY created_at",
                (case_id,),
            ).fetchall()
            files = []
            for row in rows:
                d = dict(row)
                d["validation_errors"] = json.loads(d.get("validation_errors", "[]"))
                d["metadata"] = json.loads(d.get("metadata", "{}"))
                files.append(cls.to_public_dict(d))
            return files

    @classmethod
    def get_file(cls, file_id: str) -> dict[str, Any] | None:
        """Get a single file by ID (safe public record)."""
        with get_db() as conn:
            row = conn.execute("SELECT * FROM files WHERE id = ?", (file_id,)).fetchone()
            if row is None:
                return None
            d = dict(row)
            d["validation_errors"] = json.loads(d.get("validation_errors", "[]"))
            d["metadata"] = json.loads(d.get("metadata", "{}"))
            return cls.to_public_dict(d)


file_service = FileService()
