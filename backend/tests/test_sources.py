"""Gate 1 — data source registry and provenance manifest tests.

Covers:
- The registry is seeded with the official sources and required fields.
- Status derivation is honest: never "connected" without a real probe,
  "authentication required" when credentials are absent, local-file-workflow
  sources report their own status.
- The /test endpoint persists real probe results (monkeypatched here so the
  suite never depends on live providers) and never leaks credential values.
- Every registered file gets a provenance manifest with checksum, size, media
  format and a granular validation status reflecting the real geospatial
  runtime.
"""

import io
import sys
import types
from typing import ClassVar

from app import config as app_config
from app.services import geo_runtime
from app.services.source_registry import (
    STATUS_AUTH_REQUIRED,
    STATUS_CONNECTED,
    STATUS_LOCAL_FILE,
    STATUS_NOT_VERIFIED,
    STATUS_UNAVAILABLE,
)


def _create_case(client) -> str:
    response = client.post("/api/cases", json={"title": "Registry Test Case"})
    assert response.status_code == 201
    return response.json()["data"]["id"]


def _make_tiff_bytes(size: int = 4096) -> bytes:
    return b"II\x2a\x00" + b"\x00" * max(size - 4, 0)


def _upload(client, case_id: str, filename: str, file_type: str, content: bytes, extra=None):
    data = {"file_type": file_type}
    if extra:
        data.update(extra)
    return client.post(
        f"/api/cases/{case_id}/files",
        files={"file": (filename, io.BytesIO(content), "application/octet-stream")},
        data=data,
    )


class TestSourceRegistry:
    def test_registry_seeded_with_official_sources(self, client):
        """All six official sources exist with required fields."""
        response = client.get("/api/sources")
        assert response.status_code == 200
        sources = response.json()["data"]
        ids = {s["source_id"] for s in sources}
        assert ids == {
            "sentinel1_cdse",
            "satellite_context_nasa_gibs",
            "ocean_currents_copernicus_marine",
            "wind_netcdf_grib",
            "ais_local_csv_parquet",
            "ais_gfw",
        }
        for source in sources:
            for field in (
                "source_id",
                "source_name",
                "organization",
                "data_category",
                "access_method",
                "licence",
                "configured_status",
                "authentication_required",
                "authentication_configured",
            ):
                assert field in source, f"missing {field} on {source['source_id']}"

    def test_honest_statuses_without_credentials(self, client):
        """Credential-gated sources say so; keyless and local sources are honest."""
        sources = {s["source_id"]: s for s in client.get("/api/sources").json()["data"]}

        assert sources["sentinel1_cdse"]["configured_status"] == STATUS_AUTH_REQUIRED
        assert (
            sources["ocean_currents_copernicus_marine"]["configured_status"] == STATUS_AUTH_REQUIRED
        )
        assert sources["ais_gfw"]["configured_status"] == STATUS_AUTH_REQUIRED
        # Keyless GIBS is never "connected" until a real probe succeeds.
        assert sources["satellite_context_nasa_gibs"]["configured_status"] == STATUS_NOT_VERIFIED
        # Local-file workflow sources need no provider probe.
        assert sources["wind_netcdf_grib"]["configured_status"] == STATUS_LOCAL_FILE
        assert sources["ais_local_csv_parquet"]["configured_status"] == STATUS_LOCAL_FILE

    def test_probe_success_persists_connected(self, client, monkeypatch):
        """A successful real probe flips the status to connected."""
        registry = _registry(client)
        monkeypatch.setattr(registry, "_run_probe", lambda probe, gate: (True, "none"))
        response = client.post("/api/sources/satellite_context_nasa_gibs/test")
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["configured_status"] == STATUS_CONNECTED
        assert data["last_successful_access"] is not None
        assert data["last_failed_access"] is None

    def test_probe_failure_persists_unavailable(self, client, monkeypatch):
        """A failed real probe flips the status to source_unavailable."""
        registry = _registry(client)
        monkeypatch.setattr(registry, "_run_probe", lambda probe, gate: (False, "timeout"))
        response = client.post("/api/sources/satellite_context_nasa_gibs/test")
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["configured_status"] == STATUS_UNAVAILABLE
        assert data["latest_error_category"] == "timeout"
        assert data["last_failed_access"] is not None

    def test_test_endpoint_local_workflow_no_network(self, client):
        """Local-file-workflow sources report status without any probe."""
        response = client.post("/api/sources/wind_netcdf_grib/test")
        assert response.status_code == 200
        assert response.json()["data"]["configured_status"] == STATUS_LOCAL_FILE

    def test_test_endpoint_auth_required_no_credentials(self, client):
        """Credential-gated sources cannot be probed without credentials."""
        response = client.post("/api/sources/ocean_currents_copernicus_marine/test")
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["configured_status"] == STATUS_AUTH_REQUIRED
        assert data["latest_error_category"] == "authentication"
        assert data["authentication_configured"] is False

    def test_unknown_source_404(self, client):
        response = client.get("/api/sources/not_a_source")
        assert response.status_code == 404
        response = client.post("/api/sources/not_a_source/test")
        assert response.status_code == 404

    def test_credentials_never_leak(self, client, monkeypatch):
        """Configured credential values never appear in any response."""
        monkeypatch.setattr(app_config.settings, "CDSE_CLIENT_ID", "cdse-secret-client-id-xyz")
        monkeypatch.setattr(
            app_config.settings, "CDSE_CLIENT_SECRET", "cdse-secret-client-secret-xyz"
        )
        monkeypatch.setattr(app_config.settings, "COPERNICUS_MARINE_USERNAME", "marine-user-xyz")
        monkeypatch.setattr(app_config.settings, "COPERNICUS_MARINE_PASSWORD", "marine-pass-xyz")
        monkeypatch.setattr(app_config.settings, "GFW_API_TOKEN", "gfw-token-xyz")

        for endpoint in ("/api/sources", "/api/sources/sentinel1_cdse/test"):
            response = client.post(endpoint) if endpoint.endswith("/test") else client.get(endpoint)
            assert response.status_code == 200
            text = response.text
            for secret in (
                "cdse-secret-client-id-xyz",
                "cdse-secret-client-secret-xyz",
                "marine-user-xyz",
                "marine-pass-xyz",
                "gfw-token-xyz",
            ):
                assert secret not in text
            # The masked boolean flips instead.
            if "sentinel1_cdse" in endpoint:
                assert response.json()["data"]["authentication_configured"] is True


class TestFileManifests:
    def test_manifest_created_on_upload(self, client, monkeypatch):
        """Every registered file gets a manifest with real provenance fields."""
        monkeypatch.setattr(geo_runtime, "probe_geo_runtime", lambda force=False: "import_failed")
        case_id = _create_case(client)
        content = _make_tiff_bytes()
        response = _upload(client, case_id, "scene.tif", "sar", content)
        assert response.status_code == 201
        file_id = response.json()["data"]["id"]

        manifest_response = client.get(f"/api/cases/{case_id}/files/{file_id}/manifest")
        assert manifest_response.status_code == 200
        manifest = manifest_response.json()["data"]

        import hashlib

        assert manifest["file_id"] == file_id
        assert manifest["case_id"] == case_id
        assert manifest["original_filename"] == "scene.tif"
        assert manifest["byte_size"] == len(content)
        assert manifest["sha256_checksum"] == hashlib.sha256(content).hexdigest()
        assert manifest["media_format"] == "image/tiff"
        assert manifest["source_id"] == "sentinel1_cdse"
        assert manifest["source_type"] == "sar"
        assert manifest["software_version"] == app_config.settings.APP_VERSION
        # No absolute filesystem path in the manifest.
        assert "file_path" not in manifest
        assert "uploads" not in manifest["stored_filename"]

    def test_sar_manifest_processing_blocked_without_runtime(self, client, monkeypatch):
        """Rasterio unavailable => processing_blocked, never a false ready."""
        monkeypatch.setattr(geo_runtime, "probe_geo_runtime", lambda force=False: "import_failed")
        case_id = _create_case(client)
        response = _upload(client, case_id, "scene.tif", "sar", _make_tiff_bytes())
        file_id = response.json()["data"]["id"]
        manifest = client.get(f"/api/cases/{case_id}/files/{file_id}/manifest").json()["data"]
        assert manifest["validation_status"] == "processing_blocked"
        assert any("runtime unavailable" in m for m in manifest["validation_messages"])

    def test_sar_manifest_geospatial_validated_with_runtime(self, client, monkeypatch):
        """Rasterio available + readable raster => geospatial_validated."""
        monkeypatch.setattr(geo_runtime, "probe_geo_runtime", lambda force=False: "available")
        monkeypatch.setitem(
            sys.modules,
            "rasterio",
            _fake_rasterio(raises=False),
        )
        case_id = _create_case(client)
        response = _upload(client, case_id, "scene.tif", "sar", _make_tiff_bytes())
        file_id = response.json()["data"]["id"]
        manifest = client.get(f"/api/cases/{case_id}/files/{file_id}/manifest").json()["data"]
        assert manifest["validation_status"] == "geospatial_validated"
        assert manifest["crs"] == "EPSG:4326"
        assert manifest["spatial_bounds"]["left"] == 60.0
        assert manifest["bands"] == [{"index": 1, "dtype": "float32"}]

    def test_sar_manifest_source_verified_with_declared_provenance(self, client, monkeypatch):
        """Declared provenance upgrades the status but stays honest about scope."""
        monkeypatch.setattr(geo_runtime, "probe_geo_runtime", lambda force=False: "available")
        monkeypatch.setitem(sys.modules, "rasterio", _fake_rasterio(raises=False))
        case_id = _create_case(client)
        response = _upload(
            client,
            case_id,
            "scene.tif",
            "sar",
            _make_tiff_bytes(),
            extra={
                "product_identifier": "S1A_IW_GRDH_1SDV_20260624T085300_20260624T085325_055000_06A9B0_ABCD",
                "acquisition_time": "2026-06-24T08:53:00Z",
                "provenance_source": "Copernicus Data Space Ecosystem",
                "polarization": "VV",
            },
        )
        assert response.status_code == 201
        file_id = response.json()["data"]["id"]
        manifest = client.get(f"/api/cases/{case_id}/files/{file_id}/manifest").json()["data"]
        assert manifest["validation_status"] == "source_verified"
        assert manifest["product_identifier"].startswith("S1A_IW_GRDH_1SDV_")
        assert manifest["acquisition_start"] == "2026-06-24T08:53:00.000Z"
        assert manifest["provider"] == "Copernicus Data Space Ecosystem"
        assert any("separate later gate" in m for m in manifest["validation_messages"])

    def test_sar_manifest_rejected_unreadable_raster(self, client, monkeypatch):
        """Rasterio available but raster unreadable => rejected, not validated."""
        monkeypatch.setattr(geo_runtime, "probe_geo_runtime", lambda force=False: "available")
        monkeypatch.setitem(sys.modules, "rasterio", _fake_rasterio(raises=True))
        case_id = _create_case(client)
        response = _upload(client, case_id, "scene.tif", "sar", _make_tiff_bytes())
        assert response.status_code == 201
        file_id = response.json()["data"]["id"]
        manifest = client.get(f"/api/cases/{case_id}/files/{file_id}/manifest").json()["data"]
        assert manifest["validation_status"] == "rejected"
        assert any("could not be opened" in m for m in manifest["validation_messages"])

    def test_manifest_case_isolation(self, client):
        """A manifest cannot be fetched through another case's id."""
        case_a = _create_case(client)
        case_b = _create_case(client)
        response = _upload(client, case_a, "data.tif", "mask", _make_tiff_bytes())
        file_id = response.json()["data"]["id"]

        assert client.get(f"/api/cases/{case_a}/files/{file_id}/manifest").status_code == 200
        assert client.get(f"/api/cases/{case_b}/files/{file_id}/manifest").status_code == 404
        assert client.get(f"/api/cases/{case_a}/files/no-such-file/manifest").status_code == 404

    def test_file_record_exposes_manifest_id(self, client):
        """The file listing links to its manifest id."""
        case_id = _create_case(client)
        response = _upload(
            client, case_id, "mask.png", "mask", b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
        )
        file_id = response.json()["data"]["id"]
        listing = client.get(f"/api/cases/{case_id}/files").json()["data"]
        assert listing[0]["manifest_id"].startswith("manifest-")
        assert listing[0]["id"] == file_id


def _registry(client):
    """Access the singleton registry used by the running app."""
    from app.services.source_registry import source_registry

    return source_registry


def _fake_rasterio(raises: bool):
    """A stub rasterio module for deterministic manifest tests."""
    if raises:

        def open_stub(*args, **kwargs):
            raise RuntimeError("corrupt raster")

    else:

        class _FakeSrc:
            class _Crs:
                @staticmethod
                def to_string():
                    return "EPSG:4326"

            class _Bounds:
                left = 60.0
                bottom = 10.0
                right = 61.0
                top = 11.0

            crs = _Crs()
            bounds = _Bounds()
            count = 1
            dtypes: ClassVar[list[str]] = ["float32"]

            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

        def open_stub(*args, **kwargs):
            return _FakeSrc()

    fake = types.ModuleType("rasterio")
    fake.open = open_stub
    return fake
