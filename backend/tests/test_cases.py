"""Tests for case management API endpoints."""

import json
from datetime import UTC, datetime, timedelta


class TestCaseValidation:
    """Timestamp and bounding-box semantic validation (structured 422)."""

    def _detail(self, response):
        """Normalize the 422 detail body into [(loc, msg)]."""
        body = response.json()
        detail = body.get("detail")
        if isinstance(detail, dict):
            return [(json.dumps(detail.get("errors")), detail.get("message", ""))]
        if isinstance(detail, list):
            return [(",".join(str(x) for x in d.get("loc", [])), d.get("msg", "")) for d in detail]
        return [(str(detail), str(detail))]

    def test_naive_timestamp_rejected(self, client):
        response = client.post(
            "/api/cases",
            json={"title": "T", "incident_time": "2024-01-15T10:30:00"},
        )
        assert response.status_code == 422
        assert any("timezone" in msg for _, msg in self._detail(response))

    def test_malformed_timestamp_rejected(self, client):
        response = client.post(
            "/api/cases",
            json={"title": "T", "observation_time": "not-a-timestamp"},
        )
        assert response.status_code == 422

    def test_timestamp_normalized_to_utc(self, client):
        response = client.post(
            "/api/cases",
            json={
                "title": "T",
                "incident_time": "2024-01-15T10:30:00+05:30",
            },
        )
        assert response.status_code == 201
        stored = response.json()["data"]["incident_time"]
        assert stored.endswith("Z")
        # 10:30 +05:30 == 05:00 UTC
        assert stored.startswith("2024-01-15T05:00:00")

    def test_incident_after_observation_rejected(self, client):
        response = client.post(
            "/api/cases",
            json={
                "title": "T",
                "incident_time": "2024-01-15T12:00:00Z",
                "observation_time": "2024-01-15T10:00:00Z",
            },
        )
        assert response.status_code == 422
        assert any("incident_time" in loc for loc, _ in self._detail(response))

    def test_historical_observation_accepted(self, client):
        response = client.post(
            "/api/cases",
            json={
                "title": "T",
                "incident_time": "2020-03-01T00:00:00Z",
                "observation_time": "2020-03-02T00:00:00Z",
            },
        )
        assert response.status_code == 201

    def test_future_timestamp_rejected(self, client):
        future = (datetime.now(UTC) + timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
        response = client.post(
            "/api/cases",
            json={"title": "T", "incident_time": future},
        )
        assert response.status_code == 422
        assert any("future" in msg for _, msg in self._detail(response))

    def test_bbox_partial_rejected(self, client):
        response = client.post(
            "/api/cases",
            json={"title": "T", "bbox_min_lat": 15.0},
        )
        assert response.status_code == 422

    def test_bbox_inverted_latitudes_rejected(self, client):
        response = client.post(
            "/api/cases",
            json={
                "title": "T",
                "bbox_min_lat": 16.0,
                "bbox_min_lon": 68.0,
                "bbox_max_lat": 15.0,
                "bbox_max_lon": 69.0,
            },
        )
        assert response.status_code == 422
        assert any("bbox_min_lat" in loc for loc, _ in self._detail(response))

    def test_bbox_inverted_longitudes_rejected(self, client):
        response = client.post(
            "/api/cases",
            json={
                "title": "T",
                "bbox_min_lat": 15.0,
                "bbox_min_lon": 69.0,
                "bbox_max_lat": 16.0,
                "bbox_max_lon": 68.0,
            },
        )
        assert response.status_code == 422
        assert any("bbox_min_lon" in loc for loc, _ in self._detail(response))

    def test_bbox_zero_area_rejected(self, client):
        response = client.post(
            "/api/cases",
            json={
                "title": "T",
                "bbox_min_lat": 15.0,
                "bbox_min_lon": 68.0,
                "bbox_max_lat": 15.0,
                "bbox_max_lon": 69.0,
            },
        )
        assert response.status_code == 422

    def test_bbox_out_of_range_rejected(self, client):
        response = client.post(
            "/api/cases",
            json={
                "title": "T",
                "bbox_min_lat": 15.0,
                "bbox_min_lon": 68.0,
                "bbox_max_lat": 200.0,
                "bbox_max_lon": 69.0,
            },
        )
        assert response.status_code == 422

    def test_patch_cannot_introduce_invalid_chronology(self, client, sample_case_data):
        created = client.post("/api/cases", json=sample_case_data)
        case_id = created.json()["data"]["id"]
        # Patch the observation to before the incident: merged case must fail.
        response = client.patch(
            f"/api/cases/{case_id}",
            json={"observation_time": "2024-01-15T09:00:00Z"},
        )
        assert response.status_code == 422

    def test_patch_cannot_introduce_future_timestamp(self, client, sample_case_data):
        created = client.post("/api/cases", json=sample_case_data)
        case_id = created.json()["data"]["id"]
        future = (datetime.now(UTC) + timedelta(days=60)).strftime("%Y-%m-%dT%H:%M:%SZ")
        response = client.patch(f"/api/cases/{case_id}", json={"incident_time": future})
        assert response.status_code == 422


class TestCaseEndpoints:
    """Test suite for case CRUD operations."""

    def test_create_case(self, client, sample_case_data):
        """Test creating a new case returns correct data."""
        response = client.post("/api/cases", json=sample_case_data)
        assert response.status_code == 201
        data = response.json()
        assert data["success"] is True
        case = data["data"]
        assert case["title"] == sample_case_data["title"]
        assert case["description"] == sample_case_data["description"]
        assert case["region"] == sample_case_data["region"]
        assert case["status"] == "created"
        assert case["current_stage"] == "registration"
        assert case["id"].startswith("case-")
        assert "created_at" in case
        assert "updated_at" in case

    def test_create_case_missing_title(self, client):
        """Test creating case without title fails."""
        response = client.post("/api/cases", json={"description": "no title"})
        assert response.status_code == 422  # Validation error

    def test_list_cases_empty(self, client):
        """Test listing cases when none exist."""
        response = client.get("/api/cases")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"] == []
        assert data["total"] == 0

    def test_list_cases_with_data(self, client, sample_case_data):
        """Test listing cases returns created cases."""
        # Create a case first
        client.post("/api/cases", json=sample_case_data)

        response = client.get("/api/cases")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert len(data["data"]) == 1
        assert data["total"] == 1

    def test_list_cases_pagination(self, client):
        """Test pagination works correctly."""
        # Create 3 cases
        for i in range(3):
            client.post("/api/cases", json={"title": f"Case {i}"})

        # Get first page
        response = client.get("/api/cases?offset=0&limit=2")
        data = response.json()
        assert len(data["data"]) == 2
        assert data["total"] == 3

        # Get second page
        response = client.get("/api/cases?offset=2&limit=2")
        data = response.json()
        assert len(data["data"]) == 1
        assert data["total"] == 3

    def test_get_case(self, client, sample_case_data):
        """Test getting a single case by ID."""
        create_response = client.post("/api/cases", json=sample_case_data)
        case_id = create_response.json()["data"]["id"]

        response = client.get(f"/api/cases/{case_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["data"]["id"] == case_id
        assert data["data"]["title"] == sample_case_data["title"]

    def test_get_case_not_found(self, client):
        """Test getting non-existent case returns 404."""
        response = client.get("/api/cases/case-nonexistent")
        assert response.status_code == 404

    def test_update_case(self, client, sample_case_data):
        """Test updating case fields."""
        create_response = client.post("/api/cases", json=sample_case_data)
        case_id = create_response.json()["data"]["id"]

        update_data = {"title": "Updated Investigation Title", "region": "Bay of Bengal"}
        response = client.patch(f"/api/cases/{case_id}", json=update_data)
        assert response.status_code == 200
        data = response.json()
        assert data["data"]["title"] == "Updated Investigation Title"
        assert data["data"]["region"] == "Bay of Bengal"

    def test_delete_case(self, client, sample_case_data):
        """Test deleting a case."""
        create_response = client.post("/api/cases", json=sample_case_data)
        case_id = create_response.json()["data"]["id"]

        response = client.delete(f"/api/cases/{case_id}")
        assert response.status_code == 200

        # Verify deleted
        response = client.get(f"/api/cases/{case_id}")
        assert response.status_code == 404

    def test_delete_case_not_found(self, client):
        """Test deleting non-existent case returns 404."""
        response = client.delete("/api/cases/case-nonexistent")
        assert response.status_code == 404

    def test_get_case_status(self, client, sample_case_data):
        """Test getting case status."""
        create_response = client.post("/api/cases", json=sample_case_data)
        case_id = create_response.json()["data"]["id"]

        response = client.get(f"/api/cases/{case_id}/status")
        assert response.status_code == 200
        data = response.json()
        assert data["data"]["case_id"] == case_id
        assert data["data"]["status"] == "created"
        assert data["data"]["current_stage"] == "registration"
