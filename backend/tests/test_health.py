"""Tests for health check and system status endpoints."""


class TestHealthEndpoints:
    """Test suite for health-related endpoints."""

    def test_root_endpoint(self, client):
        """Test the root endpoint returns app info."""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Oilora Blue AI"
        assert "version" in data
        assert data["docs"] == "/api/docs"

    def test_health_check(self, client):
        """Test health check returns healthy status."""
        response = client.get("/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "version" in data["data"]

    def test_system_status(self, client):
        """Test system status returns expected fields."""
        response = client.get("/api/system/status")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        status = data["data"]
        assert "backend_status" in status
        assert "database_status" in status
        assert "model_available" in status
        assert "disk_space_gb" in status
        assert "local_demo_mode" in status
        assert status["backend_status"] == "healthy"
        assert status["database_status"] == "connected"
