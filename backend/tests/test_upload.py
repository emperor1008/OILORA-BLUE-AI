"""API-level tests for secure file upload behaviour.

Covers the Phase-1 upload hardening:
- Temporary upload directories are removed after success and failure.
- Unexpected backend errors are sanitized (no internal paths/stack traces) and
  include a request ID in the body and the X-Request-ID response header.
- Mask files (TIFF/PNG/JPEG) and SAR TIFF files pass magic-byte validation.
- The 2 GB logical limit is enforced (tested with a lowered limit).
"""

import io
import os

from app import config
from app.services.file_service import FileService


def _make_tiff_bytes(size: int = 4096) -> bytes:
    """A byte string that passes TIFF magic-byte checks."""
    return b"II\x2a\x00" + b"\x00" * max(size - 4, 0)


def _upload(client, case_id: str, filename: str, file_type: str, content: bytes):
    return client.post(
        f"/api/cases/{case_id}/files",
        files={"file": (filename, io.BytesIO(content), "application/octet-stream")},
        data={"file_type": file_type},
    )


def _create_case(client) -> str:
    response = client.post("/api/cases", json={"title": "Upload Test Case"})
    assert response.status_code == 201
    return response.json()["data"]["id"]


def _temp_dirs_remaining(data_dir: str) -> list[str]:
    """Temp upload dirs created by tempfile.mkdtemp start with 'tmp'."""
    if not os.path.isdir(data_dir):
        return []
    return [d for d in os.listdir(data_dir) if d.startswith("tmp")]


class TestUploadEndpoint:
    def test_upload_valid_sar_tiff(self, client):
        """A valid GeoTIFF registers with a SHA-256 checksum."""
        case_id = _create_case(client)
        response = _upload(client, case_id, "scene.tif", "sar", _make_tiff_bytes())
        assert response.status_code == 201
        data = response.json()
        assert data["success"] is True
        file_info = data["data"]
        assert file_info["file_type"] == "sar"
        assert file_info["validation_status"] == "validated"
        assert len(file_info["sha256_checksum"]) == 64

    def test_upload_valid_mask_tiff(self, client):
        """A TIFF ground-truth mask registers successfully."""
        case_id = _create_case(client)
        response = _upload(client, case_id, "mask.tif", "mask", _make_tiff_bytes())
        assert response.status_code == 201
        assert response.json()["data"]["validation_status"] == "validated"

    def test_upload_valid_mask_png(self, client):
        """A PNG ground-truth mask registers successfully (regression test for
        the previously unreachable mask magic-byte branch)."""
        case_id = _create_case(client)
        png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 1024
        response = _upload(client, case_id, "mask.png", "mask", png)
        assert response.status_code == 201
        assert response.json()["data"]["validation_status"] == "validated"

    def test_upload_corrupt_sar_rejected(self, client):
        """A corrupt SAR file returns 422 with safe validation errors."""
        case_id = _create_case(client)
        response = _upload(client, case_id, "scene.tif", "sar", b"not a tiff at all")
        assert response.status_code == 422
        detail = response.json()["detail"]
        assert detail["message"] == "File validation failed"
        assert len(detail["errors"]) > 0

    def test_upload_executable_sar_rejected(self, client):
        """An executable disguised as a TIFF is rejected."""
        case_id = _create_case(client)
        response = _upload(client, case_id, "sneaky.tif", "sar", b"MZ" + b"\x00" * 1024)
        assert response.status_code == 422
        errors = response.json()["detail"]["errors"]
        assert any("executable" in e.lower() for e in errors)

    def test_upload_oversized_rejected(self, client, monkeypatch):
        """Files above the configured size limit return 413."""
        case_id = _create_case(client)
        monkeypatch.setattr(config.settings, "MAX_UPLOAD_SIZE_MB", 1)
        response = _upload(client, case_id, "big.tif", "sar", b"\x00" * (2 * 1024 * 1024))
        assert response.status_code == 413
        assert "too large" in response.json()["detail"].lower()

    def test_upload_to_unknown_case_404(self, client):
        """Uploading to a non-existent case returns 404 before any temp dirs."""
        response = _upload(client, "case-missing", "scene.tif", "sar", _make_tiff_bytes())
        assert response.status_code == 404


class TestTempCleanup:
    def test_temp_dir_removed_after_success(self, client):
        """No temporary upload directories remain after a successful upload."""
        case_id = _create_case(client)
        _upload(client, case_id, "scene.tif", "sar", _make_tiff_bytes())
        assert _temp_dirs_remaining(config.settings.DATA_DIR) == []

    def test_temp_dir_removed_after_validation_failure(self, client):
        """No temporary upload directories remain after a rejected upload."""
        case_id = _create_case(client)
        _upload(client, case_id, "bad.tif", "sar", b"not a tiff")
        assert _temp_dirs_remaining(config.settings.DATA_DIR) == []

    def test_temp_dir_removed_after_internal_error(self, client, monkeypatch):
        """No temporary upload directories remain after an unexpected error."""
        case_id = _create_case(client)

        def boom(*args, **kwargs):
            raise RuntimeError("internal detail: C:\\Users\\secret\\paths")

        monkeypatch.setattr(FileService, "register_file", staticmethod(boom))
        _upload(client, case_id, "scene.tif", "sar", _make_tiff_bytes())
        assert _temp_dirs_remaining(config.settings.DATA_DIR) == []


class TestSafeErrorsAndRequestId:
    def test_500_does_not_leak_internals(self, client, monkeypatch):
        """Unexpected upload errors return a sanitized 500 with a request ID."""
        case_id = _create_case(client)

        def boom(*args, **kwargs):
            raise RuntimeError("internal path: C:\\Users\\secret\\oilora_blue.db")

        monkeypatch.setattr(FileService, "register_file", staticmethod(boom))
        response = _upload(client, case_id, "scene.tif", "sar", _make_tiff_bytes())

        assert response.status_code == 500
        body = response.json()
        # FastAPI HTTPException envelope: {"detail": {...}}
        detail = body["detail"]
        assert detail["message"] == "Upload failed"
        assert detail["error_code"] == "UPLOAD_FAILED"
        # No internal details leak
        raw = response.text
        assert "internal path" not in raw
        assert "C:\\Users" not in raw
        assert "oilora_blue.db" not in raw
        # Request ID present and consistent
        assert "request_id" in detail
        assert response.headers.get("X-Request-ID") == detail["request_id"]

    def test_validation_error_does_not_contain_exception_strings(self, client):
        """422 validation errors only contain safe, human-readable messages."""
        case_id = _create_case(client)
        response = _upload(client, case_id, "scene.tif", "sar", b"junk content")
        assert response.status_code == 422
        raw = response.text
        assert "Traceback" not in raw
        assert "FileService" not in raw

    def test_every_response_has_request_id(self, client):
        """All API responses carry an X-Request-ID header."""
        response = client.get("/api/health")
        assert response.status_code == 200
        assert response.headers.get("X-Request-ID")

    def test_inbound_request_id_is_propagated(self, client):
        """A client-supplied X-Request-ID is propagated on the response."""
        response = client.get("/api/health", headers={"X-Request-ID": "trace-abc-123"})
        assert response.headers.get("X-Request-ID") == "trace-abc-123"
