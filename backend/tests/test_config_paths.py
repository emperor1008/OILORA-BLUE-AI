"""Tests for CWD-independent database path resolution.

The SQLite path must resolve to the same absolute location regardless of the
process current working directory, so starting the server from the repository
root can never create a second database.
"""

import os

from app import config


def _fresh_settings(**overrides):
    """Build a Settings instance with explicit overrides.

    Explicit init kwargs take precedence over environment variables (the test
    fixture sets a per-test DATABASE_PATH), and an empty DATABASE_PATH falls
    back to the canonical default anchored at the backend directory.
    """
    return config.Settings(**{"DATABASE_PATH": "", "DATA_DIR": "", **overrides})


class TestDatabasePathResolution:
    def test_default_anchored_to_backend_dir(self):
        settings = _fresh_settings()
        expected = str((config.BACKEND_BASE_DIR / "oilora_blue.db").resolve())
        assert settings.DATABASE_PATH == expected

    def test_relative_path_anchored_to_backend_dir(self):
        settings = _fresh_settings(DATABASE_PATH="data/alt.db")
        expected = str((config.BACKEND_BASE_DIR / "data" / "alt.db").resolve())
        assert settings.DATABASE_PATH == expected

    def test_absolute_path_preserved(self):
        absolute = os.path.join(str(config.BACKEND_BASE_DIR.parent), "custom", "absolute.db")
        settings = _fresh_settings(DATABASE_PATH=absolute)
        assert settings.DATABASE_PATH == os.path.abspath(absolute)

    def test_same_path_from_different_cwds(self, monkeypatch):
        """Resolved path is identical no matter where the process is started."""
        monkeypatch.chdir(config.BACKEND_BASE_DIR)
        from_backend = _fresh_settings(DATABASE_PATH="oilora_blue.db").DATABASE_PATH

        monkeypatch.chdir(config.BACKEND_BASE_DIR.parent)
        from_root = _fresh_settings(DATABASE_PATH="oilora_blue.db").DATABASE_PATH

        from_elsewhere = _fresh_settings(DATABASE_PATH="oilora_blue.db").DATABASE_PATH

        assert from_backend == from_root == from_elsewhere
        assert from_backend == str((config.BACKEND_BASE_DIR / "oilora_blue.db").resolve())
