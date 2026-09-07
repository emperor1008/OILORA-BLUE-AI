"""Tests for scoped case deletion, test-fixture preservation, empty DB, and
absolute file-path hardening in serialized responses."""

import json
import os

from app import config

FIXTURE_DIR = os.path.join(os.path.dirname(__file__), "fixtures")
BOUNDARY_FIXTURE = os.path.join(FIXTURE_DIR, "boundary_test_fixture.geojson")

# Path fragments that must never appear in serialized API responses.
FORBIDDEN_PATH_TOKENS = [
    r"C:\\",
    r"D:\\",
    "/home/",
    "/usr/",
    "/var/",
    "data/uploads",
    "data\\uploads",
    "data/cases",
    "data\\cases",
    "storage/cases",
    "storage\\cases",
]


def _create_case(client, **overrides):
    data = {
        "title": "Cleanup Test Investigation",
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


def _upload_fixture(client, case_id):
    with open(BOUNDARY_FIXTURE, "rb") as fh:
        content = fh.read()
    response = client.post(
        f"/api/cases/{case_id}/files",
        data={"file_type": "boundary"},
        files={"file": ("boundary_test_fixture.geojson", content, "application/geo+json")},
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]


def _db_count(cur, table, case_id):
    return cur.execute(f"SELECT COUNT(*) FROM {table} WHERE case_id = ?", (case_id,)).fetchone()[0]


class TestScopedCaseDeletion:
    """Deleting a development/runtime case removes only its own data."""

    def test_delete_cascades_records_and_runtime_dirs(self, client):
        case_id = _create_case(client)
        _upload_fixture(client, case_id)
        # Persist a viewport for this case
        resp = client.patch(
            f"/api/cases/{case_id}/map/viewport",
            json={"center_lon": 68.5, "center_lat": 15.5, "zoom": 9},
        )
        assert resp.status_code == 200

        upload_dir = os.path.join(config.settings.UPLOADS_DIR, case_id)
        cases_dir = os.path.join(config.settings.CASES_DIR, case_id)
        assert os.path.isdir(upload_dir)

        delete_resp = client.delete(f"/api/cases/{case_id}")
        assert delete_resp.status_code == 200
        assert delete_resp.json()["success"] is True

        # Case is gone
        assert client.get(f"/api/cases/{case_id}").status_code == 404
        # Related records are gone
        import sqlite3

        con = sqlite3.connect(config.settings.DATABASE_PATH)
        cur = con.cursor()
        for table in ["files", "jobs", "audit_log", "evidence_manifests", "map_viewports"]:
            assert _db_count(cur, table, case_id) == 0, table
        con.close()
        # Runtime directories removed
        assert not os.path.isdir(upload_dir)
        assert not os.path.isdir(cases_dir)

    def test_delete_preserves_test_fixtures(self, client):
        case_id = _create_case(client)
        _upload_fixture(client, case_id)
        client.delete(f"/api/cases/{case_id}")
        # The reusable test fixture under tests/fixtures must remain on disk.
        assert os.path.isfile(BOUNDARY_FIXTURE)

    def test_delete_missing_case_returns_404(self, client):
        assert client.delete("/api/cases/case-not-there").status_code == 404

    def test_delete_only_removes_target_case(self, client):
        keep_id = _create_case(client, title="Keep Me")
        drop_id = _create_case(client, title="Drop Me")
        _upload_fixture(client, keep_id)
        client.delete(f"/api/cases/{drop_id}")
        # Kept case and its file survive
        detail = client.get(f"/api/cases/{keep_id}").json()["data"]
        assert detail["title"] == "Keep Me"
        assert len(detail["files"]) == 1


class TestEmptyDatabase:
    """A fresh database returns a valid empty case list (never auto-creates)."""

    def test_empty_case_list(self, client):
        response = client.get("/api/cases")
        assert response.status_code == 200
        data = response.json()
        assert data["data"] == []
        assert data["total"] == 0


class TestFilePathExposure:
    """Serialized API responses never expose operating-system file paths."""

    def _assert_clean(self, payload: str):
        low = payload.lower()
        assert '"file_path"' not in low
        for token in FORBIDDEN_PATH_TOKENS:
            assert token.lower() not in low, token
        # Windows drive-letter path pattern (e.g. C:\...) must be absent.
        assert "\\" not in low.replace("\\\\", ""), "unescaped backslash present"

    def test_upload_response_no_path(self, client):
        case_id = _create_case(client)
        uploaded = _upload_fixture(client, case_id)
        self._assert_clean(json.dumps(uploaded))
        assert uploaded["download_available"] is False
        assert "file_path" not in uploaded

    def test_list_files_response_no_path(self, client):
        case_id = _create_case(client)
        _upload_fixture(client, case_id)
        response = client.get(f"/api/cases/{case_id}/files")
        assert response.status_code == 200
        self._assert_clean(json.dumps(response.json()))

    def test_get_file_response_no_path(self, client):
        case_id = _create_case(client)
        uploaded = _upload_fixture(client, case_id)
        response = client.get(f"/api/cases/{case_id}/files/{uploaded['id']}")
        assert response.status_code == 200
        self._assert_clean(json.dumps(response.json()))

    def test_case_detail_response_no_path(self, client):
        case_id = _create_case(client)
        _upload_fixture(client, case_id)
        response = client.get(f"/api/cases/{case_id}")
        assert response.status_code == 200
        self._assert_clean(json.dumps(response.json()))

    def test_provenance_response_no_path(self, client):
        case_id = _create_case(client)
        _upload_fixture(client, case_id)
        response = client.get(f"/api/cases/{case_id}/map/provenance")
        assert response.status_code == 200
        self._assert_clean(json.dumps(response.json()))
