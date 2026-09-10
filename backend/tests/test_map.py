"""Tests for the interactive maritime map API and map service."""

import io
import json
import math
import os

import pytest

from app.services.map_service import (
    feature_collection_bounds,
    map_service,
    normalize_feature_collection,
)

FIXTURE_DIR = os.path.join(os.path.dirname(__file__), "fixtures")
BOUNDARY_FIXTURE = os.path.join(FIXTURE_DIR, "boundary_test_fixture.geojson")


def _create_case(client, **overrides):
    data = {
        "title": "Map Test Investigation",
        "region": "Arabian Sea",
        "bbox_min_lat": 15.0,
        "bbox_min_lon": 68.0,
        "bbox_max_lat": 16.0,
        "bbox_max_lon": 69.0,
    }
    data.update(overrides)
    response = client.post("/api/cases", json=data)
    assert response.status_code == 201, response.text
    return response.json()["data"]["id"]


def _upload(client, case_id, filename, file_type, content=None, path=None):
    if content is None:
        source = path or os.path.join(FIXTURE_DIR, filename)
        with open(source, "rb") as fh:
            content = fh.read()
    files = {"file": (filename, io.BytesIO(content), "application/octet-stream")}
    return client.post(
        f"/api/cases/{case_id}/files",
        data={"file_type": file_type},
        files=files,
    )


class TestGeoValidation:
    """Pure GeoJSON coordinate/geometry validation."""

    def test_valid_feature_collection_passes(self):
        raw = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "properties": {},
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": [[[68.0, 18.0], [69.0, 18.0], [69.0, 19.0], [68.0, 18.0]]],
                    },
                }
            ],
        }
        fc, errors = normalize_feature_collection(raw)
        assert errors == []
        assert fc["type"] == "FeatureCollection"
        bounds = feature_collection_bounds(fc)
        assert bounds["min_lat"] == 18.0
        assert bounds["max_lon"] == 69.0

    def test_invalid_longitude_rejected(self):
        raw = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "properties": {},
                    "geometry": {"type": "Point", "coordinates": [400.0, 20.0]},
                }
            ],
        }
        _, errors = normalize_feature_collection(raw)
        assert any("longitude" in e for e in errors)

    def test_invalid_latitude_rejected(self):
        raw = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "properties": {},
                    "geometry": {"type": "Point", "coordinates": [70.0, -95.0]},
                }
            ],
        }
        _, errors = normalize_feature_collection(raw)
        assert any("latitude" in e for e in errors)

    def test_nan_coordinate_rejected(self):
        raw = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "properties": {},
                    "geometry": {"type": "Point", "coordinates": [float("nan"), 20.0]},
                }
            ],
        }
        _, errors = normalize_feature_collection(raw)
        assert any("NaN or infinite" in e for e in errors)

    def test_infinite_coordinate_rejected(self):
        raw = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "properties": {},
                    "geometry": {"type": "Point", "coordinates": [70.0, math.inf]},
                }
            ],
        }
        _, errors = normalize_feature_collection(raw)
        assert any("NaN or infinite" in e for e in errors)

    def test_incorrect_geometry_rejected(self):
        raw = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "properties": {},
                    "geometry": {"type": "Polygon", "coordinates": [[[68.0, 18.0]]]},
                }
            ],
        }
        fc, errors = normalize_feature_collection(raw)
        assert fc is not None
        assert any("at least four positions" in e for e in errors)

    def test_single_feature_wrapped(self):
        raw = {
            "type": "Feature",
            "properties": {},
            "geometry": {"type": "Point", "coordinates": [70.0, 19.0]},
        }
        fc, errors = normalize_feature_collection(raw)
        assert errors == []
        assert len(fc["features"]) == 1

    def test_empty_collection_rejected(self):
        raw = {"type": "FeatureCollection", "features": []}
        _, errors = normalize_feature_collection(raw)
        assert any("no features" in e for e in errors)

    def test_non_geojson_rejected(self):
        _, errors = normalize_feature_collection([1, 2, 3])
        assert errors


class TestMapSummary:
    """Map summary reflects genuine case/file state."""

    def test_summary_with_no_files(self, client):
        case_id = _create_case(client)
        response = client.get(f"/api/cases/{case_id}/map/summary")
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["case_id"] == case_id
        assert data["bounds"]["min_lat"] == 15.0
        assert data["has_geospatial_data"] is True  # case bbox is genuine data
        assert "sar_raster" in data["unavailable_layer_ids"]
        assert data["data_integrity"] == "no_data"
        # SAR imagery missing is the root cause for every detection/drift layer
        assert any("SAR imagery" in r for r in data["missing_data"])

    def test_summary_case_without_geometry(self, client):
        case_id = _create_case(
            client, bbox_min_lat=None, bbox_min_lon=None, bbox_max_lat=None, bbox_max_lon=None
        )
        response = client.get(f"/api/cases/{case_id}/map/summary")
        data = response.json()["data"]
        assert data["bounds"] is None
        assert data["has_geospatial_data"] is False
        assert data["map_ready"] is False

    def test_summary_invalid_case(self, client):
        response = client.get("/api/cases/case-does-not-exist/map/summary")
        assert response.status_code == 404

    def test_summary_no_paths_leaked(self, client):
        case_id = _create_case(client)
        payload = json.dumps(client.get(f"/api/cases/{case_id}/map/summary").json())
        assert "file_path" not in payload
        assert "uploads" not in payload
        assert "C:\\" not in payload and "/data/" not in payload

    def test_layers_response(self, client):
        case_id = _create_case(client)
        response = client.get(f"/api/cases/{case_id}/map/layers")
        assert response.status_code == 200
        layers = response.json()["data"]["layers"]
        ids = {layer["id"] for layer in layers}
        # Typed registry is centralized server-side
        assert "investigation_area" in ids
        assert "detection_predicted" in ids
        assert "drift_backward_contour_50" in ids
        assert "ais_tracks" in ids
        area = next(l for l in layers if l["id"] == "investigation_area")
        assert area["state"] == "ready"
        detection = next(l for l in layers if l["id"] == "detection_predicted")
        assert detection["state"] == "missing_input"
        assert detection["reason"] != ""


class TestMapFeatures:
    """Feature endpoints return only genuine geometry."""

    def test_investigation_area_from_bbox(self, client):
        case_id = _create_case(client)
        response = client.get(f"/api/cases/{case_id}/map/features")
        assert response.status_code == 200
        layers = response.json()["data"]["layers"]
        area = layers["investigation_area"]
        assert area["state"] == "ready"
        fc = area["features"]
        assert fc["type"] == "FeatureCollection"
        ring = fc["features"][0]["geometry"]["coordinates"][0]
        assert ring[0] == [68.0, 15.0]

    def test_unprocessed_layers_return_typed_state(self, client):
        case_id = _create_case(client)
        response = client.get(f"/api/cases/{case_id}/map/features")
        layers = response.json()["data"]["layers"]
        detection = layers["detection_predicted"]
        assert detection["state"] == "missing_input"
        assert detection["features"] is None
        # Never a fake empty FeatureCollection for an unprocessed layer
        assert detection["reason"] != ""

    def test_boundary_geojson_fixture_renders(self, client):
        case_id = _create_case(client)
        response = _upload(client, case_id, "boundary_test_fixture.geojson", "boundary")
        assert response.status_code == 201, response.text
        layers = client.get(f"/api/cases/{case_id}/map/features").json()["data"]["layers"]
        boundary = layers["case_boundary_dataset"]
        assert boundary["state"] == "ready"
        coords = boundary["features"]["features"][0]["geometry"]["coordinates"][0]
        assert coords[0] == [68.0, 18.0]
        # The fixture must never be described as a real oil spill
        title = boundary["features"]["features"][0]["properties"]["title"]
        assert "TEST FIXTURE" in title

    def test_invalid_boundary_geojson_fails_content_check(self, client):
        case_id = _create_case(client)
        bad = json.dumps(
            {
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "properties": {},
                        "geometry": {"type": "Point", "coordinates": [999.0, 20.0]},
                    }
                ],
            }
        ).encode()
        response = _upload(client, case_id, "bad.geojson", "boundary", content=bad)
        assert response.status_code == 201, response.text
        layers = client.get(f"/api/cases/{case_id}/map/features").json()["data"]["layers"]
        boundary = layers["case_boundary_dataset"]
        assert boundary["state"] == "failed"
        assert "invalid geometry" in boundary["reason"]

    def test_case_isolation(self, client):
        case_a = _create_case(client, title="Isolation A")
        case_b = _create_case(client, title="Isolation B")
        _upload(client, case_a, "boundary_test_fixture.geojson", "boundary")
        layers_b = client.get(f"/api/cases/{case_b}/map/features").json()["data"]["layers"]
        assert layers_b["case_boundary_dataset"]["state"] == "missing_input"
        layers_a = client.get(f"/api/cases/{case_a}/map/features").json()["data"]["layers"]
        assert layers_a["case_boundary_dataset"]["state"] == "ready"

    def test_unknown_layer_rejected(self, client):
        case_id = _create_case(client)
        response = client.get(f"/api/cases/{case_id}/map/features?layer=not_a_layer")
        assert response.status_code == 400

    def test_raster_layer_not_in_features(self, client):
        case_id = _create_case(client)
        response = client.get(f"/api/cases/{case_id}/map/features?layer=sar_raster")
        assert response.status_code == 400


class TestViewport:
    """Viewport persistence (safe display preference)."""

    def test_viewport_default_from_bounds(self, client):
        case_id = _create_case(client)
        response = client.get(f"/api/cases/{case_id}/map/viewport")
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["viewport"] is None
        assert data["default_viewport"] is not None
        assert -90 <= data["default_viewport"]["center_lat"] <= 90

    def test_viewport_save_and_load(self, client):
        case_id = _create_case(client)
        payload = {
            "center_lon": 68.5,
            "center_lat": 15.5,
            "zoom": 9,
            "bearing": 0,
            "pitch": 0,
        }
        response = client.patch(f"/api/cases/{case_id}/map/viewport", json=payload)
        assert response.status_code == 200
        loaded = client.get(f"/api/cases/{case_id}/map/viewport").json()["data"]
        assert loaded["viewport"]["zoom"] == 9
        assert loaded["viewport"]["center_lon"] == 68.5

    def test_viewport_invalid_longitude_rejected(self, client):
        case_id = _create_case(client)
        payload = {"center_lon": 200.0, "center_lat": 15.0, "zoom": 9}
        response = client.patch(f"/api/cases/{case_id}/map/viewport", json=payload)
        assert response.status_code == 422

    def test_viewport_invalid_case(self, client):
        response = client.patch(
            "/api/cases/case-nope/map/viewport",
            json={"center_lon": 68.0, "center_lat": 15.0, "zoom": 8},
        )
        assert response.status_code == 404


class TestProvenance:
    """Provenance responses never leak filesystem paths."""

    def test_provenance_empty(self, client):
        case_id = _create_case(client)
        response = client.get(f"/api/cases/{case_id}/map/provenance")
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["sources"] == []
        assert data["derived_artifacts"] == []

    def test_provenance_after_upload(self, client):
        case_id = _create_case(client)
        _upload(client, case_id, "boundary_test_fixture.geojson", "boundary")
        data = client.get(f"/api/cases/{case_id}/map/provenance").json()["data"]
        assert len(data["sources"]) == 1
        source = data["sources"][0]
        assert source["file_type"] == "boundary"
        assert len(source["sha256_checksum"]) == 64
        payload = json.dumps(data)
        assert "file_path" not in payload
        assert "C:\\" not in payload


class TestSarPreview:
    """Derived SAR preview path (rasterio runtime required).

    These tests only run where the geospatial runtime really imports (the CI
    geospatial job). On installations where the native rasterio DLL cannot be
    loaded they are reported as skipped — never as passed — and the
    graceful-degradation behaviour is covered by TestGeoRuntimeDegradation.
    """

    @pytest.fixture
    def geotiff_bytes(self):
        try:
            import numpy as np
            import rasterio as rio
        except Exception as exc:  # noqa: BLE001 - any native import failure skips
            pytest.skip(f"geospatial runtime unavailable: {exc.__class__.__name__}")

        width, height = 16, 12
        # Synthetic radiance pattern - TEST FIXTURE, not an oil spill.
        x = np.linspace(-2.0, 2.0, width)
        y = np.linspace(-2.0, 2.0, height)
        xx, yy = np.meshgrid(x, y)
        data = (np.sin(xx) + np.cos(yy)).astype("float32")

        buffer = io.BytesIO()
        with rio.open(
            buffer,
            "w",
            driver="GTiff",
            width=width,
            height=height,
            count=1,
            dtype="float32",
            crs="EPSG:4326",
            transform=rio.transform.from_bounds(68.0, 15.0, 69.0, 16.0, width, height),
        ) as dst:
            dst.write(data, 1)
        buffer.seek(0)
        return buffer.read()

    @pytest.mark.geospatial
    def test_sar_upload_and_preview(self, client, geotiff_bytes):
        case_id = _create_case(client)
        response = _upload(client, case_id, "sar_fixture.tif", "sar", content=geotiff_bytes)
        assert response.status_code == 201, response.text

        overlay = client.get(f"/api/cases/{case_id}/map/sar-overlay").json()["data"]
        assert overlay["available"] is True
        assert overlay["state"] == "ready"
        assert overlay["crs"] == "EPSG:4326"
        west, _south, _east, north = overlay["bounds"]
        assert west == pytest.approx(68.0, abs=1e-4)
        assert north == pytest.approx(16.0, abs=1e-4)
        assert len(overlay["preview_sha256"]) == 64
        assert overlay["acquisition_time"] is None  # honestly not extracted yet

        # PNG endpoint serves real derived image bytes deterministically
        png = client.get(f"/api/cases/{case_id}/map/sar-preview/{overlay['file_id']}")
        assert png.status_code == 200
        assert png.headers["content-type"] == "image/png"
        assert png.content[:8] == b"\x89PNG\r\n\x1a\n"
        import hashlib

        assert hashlib.sha256(png.content).hexdigest() == overlay["preview_sha256"]

        # Provenance records the derived artifact
        prov = client.get(f"/api/cases/{case_id}/map/provenance").json()["data"]
        assert len(prov["derived_artifacts"]) == 1
        assert prov["derived_artifacts"][0]["artifact"] == "sar_grayscale_preview"
        assert prov["derived_artifacts"][0]["input_sha256"] == overlay["input_sha256"]

    def test_preview_unavailable_without_sar(self, client):
        case_id = _create_case(client)
        overlay = client.get(f"/api/cases/{case_id}/map/sar-overlay").json()["data"]
        assert overlay["available"] is False
        assert overlay["state"] == "missing_input"

    @pytest.mark.geospatial
    def test_sar_preview_wrong_case_file(self, client, geotiff_bytes):
        case_a = _create_case(client, title="A")
        response = _upload(client, case_a, "sar_fixture.tif", "sar", content=geotiff_bytes)
        assert response.status_code == 201
        file_id = response.json()["data"]["id"]
        case_b = _create_case(client, title="B")
        other = client.get(f"/api/cases/{case_b}/map/sar-preview/{file_id}")
        assert other.status_code == 404


# Minimal byte-level-valid TIFF header (LE "II\x2a\x00") plus padding. It passes
# extension + magic-byte registration but is NOT a georeferenced raster; the
# state machine must never let it appear as verified Sentinel-1 input.
MINIMAL_TIFF = b"II\x2a\x00" + b"\x00" * 64

VALID_INSPECT = {
    "epsg": 4326,
    "bounds": (68.0, 15.0, 69.0, 16.0),
    "width": 16,
    "height": 12,
    "count": 1,
    "overviews": False,
}


class TestGeoRuntimeDegradation:
    """Graceful degradation when the optional geospatial runtime cannot import.

    These tests run everywhere (no Rasterio required): they patch the service's
    capability probe to simulate an unavailable native runtime and verify the
    application stays usable for case management and vector mapping while the
    SAR layer is honestly reported as processing-blocked.
    """

    def _upload_minimal_tiff(self, client, case_id, extra_form=None):
        return _upload(
            client,
            case_id,
            "sar_fixture.tif",
            "sar",
            content=MINIMAL_TIFF,
        )

    def test_rasterio_import_failure_blocks_sar_without_false_ready(self, client, monkeypatch):
        case_id = _create_case(client)
        response = self._upload_minimal_tiff(client, case_id)
        assert response.status_code == 201, response.text

        monkeypatch.setattr(map_service, "_geo_runtime_status", lambda: "import_failed")

        layers = client.get(f"/api/cases/{case_id}/map/layers").json()["data"]["layers"]
        sar = next(layer for layer in layers if layer["id"] == "sar_raster")
        assert sar["state"] == "unavailable"
        assert "Geospatial raster runtime unavailable" in sar["reason"]
        assert sar["validation_status"] == "processing_blocked"

        overlay = client.get(f"/api/cases/{case_id}/map/sar-overlay").json()["data"]
        assert overlay["available"] is False
        assert overlay["state"] == "unavailable"
        assert overlay["validation_status"] == "processing_blocked"
        assert "Geospatial raster runtime unavailable" in overlay["reason"]
        assert "Configure a supported Rasterio runtime" in overlay["reason"]

        # The PNG endpoint must not attempt generation and must not be served.
        png = client.get(f"/api/cases/{case_id}/map/sar-preview/{response.json()['data']['id']}")
        assert png.status_code == 404

    def test_arbitrary_tiff_never_becomes_verified_sentinel1(self, client, monkeypatch):
        """A byte-level-valid TIFF with no provenance can never be Ready."""
        case_id = _create_case(client)
        response = self._upload_minimal_tiff(client, case_id)
        assert response.status_code == 201, response.text

        monkeypatch.setattr(map_service, "_geo_runtime_status", lambda: "available")
        monkeypatch.setattr(map_service, "_inspect_raster", lambda path: dict(VALID_INSPECT))

        layers = client.get(f"/api/cases/{case_id}/map/layers").json()["data"]["layers"]
        sar = next(layer for layer in layers if layer["id"] == "sar_raster")
        assert sar["state"] == "not_processed"
        assert sar["validation_status"] == "geospatial_validated"
        assert "Sentinel-1 provenance incomplete" in sar["reason"]

        overlay = client.get(f"/api/cases/{case_id}/map/sar-overlay").json()["data"]
        assert overlay["available"] is False
        # Preview generation is attempted on demand for validated rasters; the
        # fake TIFF bytes cannot be read by the real runtime, so the overlay
        # reports unavailable — it can never reach ready.
        assert overlay["state"] == "unavailable"
        assert "preview generation failed" in overlay["reason"]

    def test_invalid_raster_reported_failed(self, client, monkeypatch):
        """A registered raster that cannot be read is failed, not ready."""
        case_id = _create_case(client)
        self._upload_minimal_tiff(client, case_id)
        monkeypatch.setattr(map_service, "_geo_runtime_status", lambda: "available")

        def bad_inspect(path):
            from app.services.map_service import MapPreviewUnavailable

            raise MapPreviewUnavailable(
                "Registered SAR raster does not declare a Coordinate Reference System."
            )

        monkeypatch.setattr(map_service, "_inspect_raster", bad_inspect)
        layers = client.get(f"/api/cases/{case_id}/map/layers").json()["data"]["layers"]
        sar = next(layer for layer in layers if layer["id"] == "sar_raster")
        assert sar["state"] == "failed"
        assert sar["validation_status"] == "invalid"
        assert "Coordinate Reference System" in sar["reason"]

    def test_sentinel_metadata_promotes_to_verified_but_not_ready(self, client, monkeypatch):
        """Product identifier + source verify provenance; preview still required."""
        case_id = _create_case(client)
        self._upload_minimal_tiff(client, case_id)
        monkeypatch.setattr(map_service, "_geo_runtime_status", lambda: "available")
        monkeypatch.setattr(map_service, "_inspect_raster", lambda path: dict(VALID_INSPECT))

        # Record analyst-supplied Sentinel-1 provenance directly on the file row.
        from app.database import get_db

        with get_db() as conn:
            row = conn.execute(
                "SELECT id FROM files WHERE case_id = ? AND file_type = 'sar'", (case_id,)
            ).fetchone()
            meta = conn.execute("SELECT metadata FROM files WHERE id = ?", (row["id"],)).fetchone()[
                "metadata"
            ]
            import json as _json

            meta_obj = _json.loads(meta)
            meta_obj["product_identifier"] = (
                "S1A_IW_GRDH_1SDV_20260101T000000_20260101T000025_000000_000000_0000"
            )
            meta_obj["provenance_source"] = "Copernicus Data Space Ecosystem (test provenance)"
            conn.execute(
                "UPDATE files SET metadata = ? WHERE id = ?",
                (_json.dumps(meta_obj), row["id"]),
            )

        layers = client.get(f"/api/cases/{case_id}/map/layers").json()["data"]["layers"]
        sar = next(layer for layer in layers if layer["id"] == "sar_raster")
        assert sar["validation_status"] == "sentinel1_verified"
        assert sar["state"] == "not_processed"
        assert "preview generation required" in sar["reason"]

    def test_preview_files_promote_to_ready(self, client, monkeypatch):
        """Verified source with matching derived preview is Ready (honest)."""
        case_id = _create_case(client)
        response = self._upload_minimal_tiff(client, case_id)
        sha = response.json()["data"]["sha256_checksum"]
        monkeypatch.setattr(map_service, "_geo_runtime_status", lambda: "available")
        monkeypatch.setattr(map_service, "_inspect_raster", lambda path: dict(VALID_INSPECT))

        directory = map_service._case_map_dir(case_id)
        prefix = sha[:16]
        meta = {
            "derived_from": "sar_raster_preview",
            "input_sha256": sha,
            "preview_sha256": "ab" * 32,
            "generated_at": "2026-09-07T00:00:00.000Z",
            "bounds": [68.0, 15.0, 69.0, 16.0],
            "crs_out": "EPSG:4326",
            "width": 16,
            "height": 12,
            "band": 1,
            "config": {"max_dimension": 2048},
        }
        with open(os.path.join(directory, f"sar_preview_{prefix}.json"), "w") as fh:
            json.dump(meta, fh)
        with open(os.path.join(directory, f"sar_preview_{prefix}.png"), "wb") as fh:
            fh.write(b"\x89PNG\r\n\x1a\n" + b"\x00" * 16)

        layers = client.get(f"/api/cases/{case_id}/map/layers").json()["data"]["layers"]
        sar = next(layer for layer in layers if layer["id"] == "sar_raster")
        assert sar["state"] == "ready"
        assert sar["validation_status"] == "preview_ready"

        overlay = client.get(f"/api/cases/{case_id}/map/sar-overlay").json()["data"]
        assert overlay["available"] is True
        assert overlay["validation_status"] == "preview_ready"
        assert overlay["bounds"] == [68.0, 15.0, 69.0, 16.0]

    def test_sar_upload_provenance_validation(self, client):
        """Invalid acquisition time is rejected; valid provenance is stored."""
        case_id = _create_case(client)
        bad = _upload(
            client,
            case_id,
            "sar_fixture.tif",
            "sar",
            content=MINIMAL_TIFF,
        )
        assert bad.status_code == 201  # baseline upload works

        bad_time = client.post(
            f"/api/cases/{case_id}/files",
            data={
                "file_type": "sar",
                "acquisition_time": "2026-01-01T00:00:00",  # naive: rejected
            },
            files={
                "file": ("sar_fixture.tif", io.BytesIO(MINIMAL_TIFF), "application/octet-stream")
            },
        )
        assert bad_time.status_code == 422
        assert "acquisition_time" in json.dumps(bad_time.json())

        good = client.post(
            f"/api/cases/{case_id}/files",
            data={
                "file_type": "sar",
                "product_identifier": "S1A_IW_GRDH_1SDV_TEST",
                "acquisition_time": "2026-01-01T00:00:00Z",
                "provenance_source": "Copernicus Data Space Ecosystem",
                "polarization": "VV",
            },
            files={
                "file": ("sar_fixture.tif", io.BytesIO(MINIMAL_TIFF), "application/octet-stream")
            },
        )
        assert good.status_code == 201, good.text
        meta = good.json()["data"]["metadata"]
        assert meta["product_identifier"] == "S1A_IW_GRDH_1SDV_TEST"
        assert meta["acquisition_time"] == "2026-01-01T00:00:00.000Z"
        assert meta["polarization"] == "VV"
