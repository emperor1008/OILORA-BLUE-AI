"""
Oilora Blue AI — Geospatial Runtime Capability Probe

Shared, process-cached probe for whether the optional numpy/rasterio runtime
can actually be used. ``importlib.util.find_spec`` only proves a package is
present on disk — it says nothing about whether native DLLs load (e.g. a
Windows Application Control policy can block them). This module performs the
real import inside a controlled try/except and caches the result.

Return values:
- ``available``     — both imports succeed
- ``not_installed`` — packages are missing from the environment
- ``import_failed`` — packages exist but the native runtime cannot be loaded
                      (blocked DLL, missing native dependency, ...)
"""

import logging

logger = logging.getLogger("oilora_blue.geo_runtime")

_cache: dict[str, str] = {}


def probe_geo_runtime(force: bool = False) -> str:
    """Return the real runtime status, importing numpy/rasterio at most once.

    ``force`` bypasses the process cache (used by tests that install or remove
    packages in the same process). Technical detail is logged server-side only;
    clients receive safe, actionable text instead of stack traces.
    """
    if not force and _cache.get("status") is not None:
        return _cache["status"]
    try:
        import numpy  # noqa: F401
        import rasterio  # noqa: F401

        status = "available"
    except ModuleNotFoundError:
        status = "not_installed"
        logger.warning("Geospatial runtime is not installed (numpy/rasterio).")
    except Exception as exc:  # noqa: BLE001 - native import failure (e.g. blocked DLL)
        status = "import_failed"
        logger.warning("Geospatial runtime import failed: %s", exc)
    _cache["status"] = status
    return status


def geo_runtime_available() -> bool:
    """True only when the real import probe reports a working runtime."""
    return probe_geo_runtime() == "available"
