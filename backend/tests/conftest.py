"""
Oilora Blue AI — Test Configuration

Pytest fixtures for testing the backend API.
"""

import os
import sys

import pytest

# Add the parent directory to sys.path so we can import the app
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# Override settings before importing anything else
os.environ["DATABASE_PATH"] = ""  # Will be set in fixture
os.environ["DATA_DIR"] = ""  # Will be set in fixture
os.environ["DEBUG"] = "true"
os.environ["ENABLE_LOCAL_DEMO_MODE"] = "true"
os.environ["LOG_LEVEL"] = "WARNING"


@pytest.fixture(autouse=True)
def setup_test_env(tmp_path):
    """Set up isolated test environment for each test."""
    test_data_dir = str(tmp_path / "data")
    test_db_path = str(tmp_path / "test_oilora.db")

    os.environ["DATA_DIR"] = test_data_dir
    os.environ["DATABASE_PATH"] = test_db_path
    os.environ["CASES_DIR"] = str(tmp_path / "data" / "cases")
    os.environ["UPLOADS_DIR"] = str(tmp_path / "data" / "uploads")
    os.environ["OUTPUTS_DIR"] = str(tmp_path / "data" / "outputs")
    os.environ["MODELS_DIR"] = str(tmp_path / "models")

    # Reinitialize settings
    import app.config as config_module

    config_module.settings = config_module.Settings()

    # Initialize database
    from app.database import close_database, init_database

    close_database()
    init_database()

    yield tmp_path

    # Cleanup
    close_database()


@pytest.fixture
def client(setup_test_env):
    """Create a test client for the FastAPI app.

    Settings are already updated by setup_test_env before this runs,
    so the app lifespan will use the correct test database path.
    """
    from fastapi.testclient import TestClient

    from app.main import app

    return TestClient(app)


@pytest.fixture
def sample_case_data():
    """Sample case creation data."""
    return {
        "title": "Test Oil Spill Investigation",
        "description": "Test case for the Arabian Sea",
        "region": "Arabian Sea",
        "incident_time": "2024-01-15T10:30:00Z",
        "observation_time": "2024-01-15T12:00:00Z",
        "bbox_min_lat": 15.0,
        "bbox_min_lon": 68.0,
        "bbox_max_lat": 16.0,
        "bbox_max_lon": 69.0,
        "analyst_notes": "Suspected oil spill near shipping lane",
    }
