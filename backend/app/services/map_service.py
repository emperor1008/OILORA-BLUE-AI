"""
Oilora Blue AI — Interactive Map Service

Builds the honest, real-data layer registry for the investigation workspace.

Only layers backed by genuine data are reported as ready. Scientific stages that
have not been executed (detection, drift, AIS analysis) are reported with typed
not_processed / missing_input states and human-readable reasons - never with
fabricated geometry.

Real data handled here today:
- Case bounding box        -> investigation-area polygon (from SQLite case rows)
- Registered boundary GeoJSON file -> validated FeatureCollection
- Registered SAR GeoTIFF   -> derived grayscale PNG preview (rasterio, optional)
  cached per input SHA-256 and recorded as a derived artifact.

The rasterio/numpy runtime is optional: when absent the SAR preview layer is
reported honestly as unavailable and every other map capability keeps working.
"""

from __future__ import annotations

import json
import logging
import math
import os
import struct
import threading
import zlib
from datetime import UTC, datetime
from typing import Any

from .. import config
from ..database import get_db
from ..services.case_service import case_service
from ..services.file_service import FileService

logger = logging.getLogger("oilora_blue.map")

# Honest processing-blocked copy shown in the layer panel / SAR overlay when
# the optional geospatial runtime cannot be imported on this installation.
SAR_RUNTIME_UNAVAILABLE_REASON = (
    "Geospatial raster runtime unavailable. The registered file cannot be "
    "processed on this installation. Configure a supported Rasterio runtime "
    "before generating a SAR overlay."
)

# ─── Registry ─────────────────────────────────────────────────────────

# Layer metadata (id, name, category, kind, flags). Ordering is z-order:
# context first, scientific layers above.
_LAYER_DEFS: list[dict[str, Any]] = [
    {
        "id": "investigation_area",
        "name": "Investigation Area",
        "category": "Context",
        "kind": "vector",
        "selectable": True,
        "timeline": False,
        "exportable": True,
        "legend": {
            "title": "Investigation area",
            "items": [
                {
                    "label": "Registered case bounds",
                    "color": "#0E7490",
                    "dash": [4, 3],
                    "width": 2,
                    "fill": "rgba(14, 116, 144, 0.06)",
                }
            ],
        },
    },
    {
        "id": "case_boundary_dataset",
        "name": "Case Boundary",
        "category": "Context",
        "kind": "vector",
        "selectable": True,
        "timeline": False,
        "exportable": True,
        "legend": {
            "title": "Known geographic boundary",
            "items": [
                {
                    "label": "Registered GeoJSON boundary",
                    "color": "#0B2A3D",
                    "width": 1.5,
                    "fill": "rgba(11, 42, 61, 0.05)",
                }
            ],
        },
    },
    {
        "id": "coastline",
        "name": "Coastline",
        "category": "Context",
        "kind": "vector",
        "selectable": False,
        "timeline": False,
        "exportable": False,
        "legend": {
            "title": "Coastline",
            "items": [{"label": "Shoreline", "color": "#64748B", "width": 1}],
        },
    },
    {
        "id": "sar_raster",
        "name": "Sentinel-1 SAR Source",
        "category": "Satellite",
        "kind": "raster",
        "selectable": False,
        "timeline": True,
        "exportable": False,
        "opacity_default": 1.0,
        "legend": {
            "title": "Scientific Sentinel-1 SAR (context basemap is not SAR)",
            "items": [
                {
                    "label": "Radar backscatter (grayscale preview)",
                    "color": "#94A3B8",
                    "fill": "rgba(148, 163, 184, 0.9)",
                }
            ],
        },
    },
    {
        "id": "detection_probability",
        "name": "Oil Probability",
        "category": "Detection",
        "kind": "raster",
        "selectable": False,
        "timeline": True,
        "exportable": False,
        "opacity_default": 0.8,
        "legend": {
            "title": "Model probability (0-1)",
            "items": [
                {"label": "Low", "color": "#CBDDE5"},
                {"label": "Medium", "color": "#22D3EE"},
                {"label": "High", "color": "#0891B2"},
                {"label": "Very high", "color": "#F59E0B"},
            ],
        },
    },
    {
        "id": "detection_predicted",
        "name": "AI-Predicted Oil Boundary",
        "category": "Detection",
        "kind": "vector",
        "selectable": True,
        "timeline": True,
        "exportable": True,
        "legend": {
            "title": "Model prediction (unreviewed)",
            "items": [
                {
                    "label": "Predicted slick boundary",
                    "color": "#F59E0B",
                    "dash": [5, 4],
                    "width": 2,
                    "fill": "rgba(245, 158, 11, 0.12)",
                }
            ],
        },
    },
    {
        "id": "detection_reviewed",
        "name": "Analyst-Reviewed Oil Boundary",
        "category": "Detection",
        "kind": "vector",
        "selectable": True,
        "timeline": True,
        "exportable": True,
        "legend": {
            "title": "Accepted after human review",
            "items": [
                {
                    "label": "Reviewed slick boundary",
                    "color": "#EF5B5B",
                    "width": 2.5,
                    "fill": "rgba(239, 91, 91, 0.15)",
                }
            ],
        },
    },
    {
        "id": "detection_ground_truth",
        "name": "Ground-Truth Boundary",
        "category": "Detection",
        "kind": "vector",
        "selectable": True,
        "timeline": True,
        "exportable": True,
        "legend": {
            "title": "Provided reference labels",
            "items": [
                {
                    "label": "Ground-truth boundary",
                    "color": "#10B981",
                    "dash": [2, 2],
                    "width": 1.5,
                }
            ],
        },
    },
    {
        "id": "drift_backward_particles",
        "name": "Backward Drift Particles",
        "category": "Drift",
        "kind": "vector",
        "selectable": False,
        "timeline": True,
        "exportable": True,
        "legend": {
            "title": "Ensemble particle trajectories",
            "items": [{"label": "Simulated particle", "color": "#0E7490", "symbol": "dot"}],
        },
    },
    {
        "id": "drift_backward_contour_50",
        "name": "Origin Zone - 50% Contour",
        "category": "Drift",
        "kind": "vector",
        "selectable": True,
        "timeline": False,
        "exportable": True,
        "legend": {
            "title": "Probable origin (backward)",
            "items": [{"label": "50% origin contour", "color": "#0B2A3D", "width": 2.5}],
        },
    },
    {
        "id": "drift_backward_contour_75",
        "name": "Origin Zone - 75% Contour",
        "category": "Drift",
        "kind": "vector",
        "selectable": True,
        "timeline": False,
        "exportable": True,
        "legend": {
            "title": "Probable origin (backward)",
            "items": [{"label": "75% origin contour", "color": "#0E7490", "width": 2}],
        },
    },
    {
        "id": "drift_backward_contour_90",
        "name": "Origin Zone - 90% Contour",
        "category": "Drift",
        "kind": "vector",
        "selectable": True,
        "timeline": False,
        "exportable": True,
        "legend": {
            "title": "Probable origin (backward)",
            "items": [
                {
                    "label": "90% origin contour",
                    "color": "#22D3EE",
                    "width": 1.5,
                    "fill": "rgba(34, 211, 238, 0.08)",
                }
            ],
        },
    },
    {
        "id": "drift_forward_particles",
        "name": "Forward Drift Particles",
        "category": "Drift",
        "kind": "vector",
        "selectable": False,
        "timeline": True,
        "exportable": True,
        "legend": {
            "title": "Ensemble particle trajectories",
            "items": [{"label": "Simulated particle", "color": "#0891B2", "symbol": "dot"}],
        },
    },
    {
        "id": "drift_forward_contours",
        "name": "Forward Probability Contours",
        "category": "Drift",
        "kind": "vector",
        "selectable": True,
        "timeline": True,
        "exportable": True,
        "legend": {
            "title": "Forward prediction",
            "items": [
                {
                    "label": "Forecast probability contour",
                    "color": "#0891B2",
                    "dash": [3, 3],
                    "width": 1.5,
                    "fill": "rgba(8, 145, 178, 0.08)",
                }
            ],
        },
    },
    {
        "id": "drift_coastline_contact",
        "name": "Potential Coastline Contact",
        "category": "Drift",
        "kind": "vector",
        "selectable": True,
        "timeline": True,
        "exportable": True,
        "legend": {
            "title": "Coastline-contact indicator",
            "items": [{"label": "Contact region", "color": "#EF5B5B", "symbol": "hatch"}],
        },
    },
    {
        "id": "wind_vectors",
        "name": "Wind Vectors",
        "category": "Environment",
        "kind": "vector",
        "selectable": False,
        "timeline": True,
        "exportable": True,
        "legend": {
            "title": "Wind forcing",
            "items": [{"label": "Wind vector", "color": "#0E7490", "symbol": "arrow"}],
        },
    },
    {
        "id": "current_vectors",
        "name": "Ocean-Current Vectors",
        "category": "Environment",
        "kind": "vector",
        "selectable": False,
        "timeline": True,
        "exportable": True,
        "legend": {
            "title": "Current forcing",
            "items": [{"label": "Current vector", "color": "#0891B2", "symbol": "arrow"}],
        },
    },
    {
        "id": "env_coverage",
        "name": "Environmental Coverage",
        "category": "Environment",
        "kind": "vector",
        "selectable": False,
        "timeline": False,
        "exportable": False,
        "legend": {
            "title": "Forcing data extent",
            "items": [{"label": "Coverage boundary", "color": "#CBDDE5", "dash": [2, 3]}],
        },
    },
    {
        "id": "ais_tracks",
        "name": "AIS Vessel Tracks",
        "category": "Vessels",
        "kind": "vector",
        "selectable": True,
        "timeline": True,
        "exportable": True,
        "legend": {
            "title": "Vessel movement",
            "items": [{"label": "AIS track", "color": "#94A3B8", "width": 1.5}],
        },
    },
    {
        "id": "ais_candidate_tracks",
        "name": "Candidate Vessel Tracks",
        "category": "Vessels",
        "kind": "vector",
        "selectable": True,
        "timeline": True,
        "exportable": True,
        "legend": {
            "title": "Ranked candidate vessels",
            "items": [{"label": "Candidate track", "color": "#0891B2", "width": 2}],
        },
    },
    {
        "id": "ais_gap_segments",
        "name": "AIS Gap Segments",
        "category": "Vessels",
        "kind": "vector",
        "selectable": False,
        "timeline": True,
        "exportable": True,
        "legend": {
            "title": "Signal gaps",
            "items": [{"label": "Interpolated / gap segment", "color": "#F59E0B", "dash": [2, 2]}],
        },
    },
    {
        "id": "ais_closest_approach",
        "name": "Closest-Approach Points",
        "category": "Vessels",
        "kind": "vector",
        "selectable": True,
        "timeline": False,
        "exportable": True,
        "legend": {
            "title": "Geometry proximity",
            "items": [{"label": "Closest-approach point", "color": "#EF5B5B", "symbol": "marker"}],
        },
    },
    {
        "id": "ais_origin_intersections",
        "name": "Origin-Zone Intersections",
        "category": "Vessels",
        "kind": "vector",
        "selectable": True,
        "timeline": False,
        "exportable": True,
        "legend": {
            "title": "Spatial match with origin zone",
            "items": [{"label": "Intersection point", "color": "#F59E0B", "symbol": "diamond"}],
        },
    },
]

_VECTOR_LAYER_IDS = {d["id"] for d in _LAYER_DEFS if d["kind"] == "vector"}
_RASTER_LAYER_IDS = {d["id"] for d in _LAYER_DEFS if d["kind"] == "raster"}
_LAYER_BY_ID = {d["id"]: d for d in _LAYER_DEFS}

# ─── GeoJSON validation (pure, dependency-free) ───────────────────────

_GEOM_TYPES = {
    "Point",
    "MultiPoint",
    "LineString",
    "MultiLineString",
    "Polygon",
    "MultiPolygon",
    "GeometryCollection",
}


def _iter_coordinates(geometry: dict[str, Any]):
    """Yield coordinate tuples from a GeoJSON geometry (assumes valid structure)."""
    gtype = geometry.get("type")
    coords = geometry.get("coordinates")
    if gtype == "GeometryCollection":
        for child in geometry.get("geometries", []) or []:
            yield from _iter_coordinates(child)
    elif isinstance(coords, list):
        if gtype in {"Point", "MultiPoint"} and coords and isinstance(coords[0], (int, float)):
            yield coords
        elif gtype == "LineString" and coords and isinstance(coords[0], list):
            for c in coords:
                yield c
        elif gtype == "Polygon":
            for ring in coords:
                for c in ring:
                    yield c
        else:
            # MultiLineString / MultiPolygon / nested structures
            def walk(items: list) -> None:
                for item in items:
                    if isinstance(item, list) and item and isinstance(item[0], (int, float)):
                        yield item  # type: ignore[misc]
                    elif isinstance(item, list):
                        yield from walk(item)

            yield from walk(coords)


def _geometry_structure_errors(geometry: dict[str, Any]) -> list[str]:
    """Structural GeoJSON geometry checks (min positions, ring closure)."""
    errors: list[str] = []
    gtype = geometry.get("type")
    coords = geometry.get("coordinates") or []
    if not isinstance(coords, list):
        return ["geometry coordinates are not a list."]

    def check_polygon(polygon: list) -> None:
        if not isinstance(polygon, list) or not polygon:
            errors.append("Polygon contains an empty ring list.")
            return
        for ring in polygon:
            if not isinstance(ring, list) or len(ring) < 4:
                errors.append("Polygon ring must contain at least four positions.")
            elif ring[0] != ring[-1]:
                errors.append("Polygon ring must be closed (first == last position).")

    if gtype in {"Point", "MultiPoint"} and not coords:
        errors.append(f"{gtype} contains no coordinates.")
    elif gtype == "LineString":
        if not coords:
            errors.append("LineString contains no coordinates.")
        elif len(coords) < 2:
            errors.append("LineString must contain at least two positions.")
    elif gtype == "MultiLineString":
        if not coords:
            errors.append("MultiLineString contains no coordinates.")
        else:
            for i, line in enumerate(coords):
                if not isinstance(line, list) or len(line) < 2:
                    errors.append(f"MultiLineString part {i} must contain at least two positions.")
    elif gtype == "Polygon":
        check_polygon(coords)
    elif gtype == "MultiPolygon":
        if not coords:
            errors.append("MultiPolygon contains no polygons.")
        else:
            for i, polygon in enumerate(coords):
                if not isinstance(polygon, list) or not polygon:
                    errors.append(f"MultiPolygon part {i} is empty.")
                    continue
                check_polygon(polygon)
    return errors


def _validate_coordinate(
    coord: list, feature_index: int, coord_index: int, errors: list[str]
) -> None:
    if not isinstance(coord, (list, tuple)) or len(coord) < 2:
        errors.append(
            f"Feature {feature_index}: coordinate {coord_index} must be [longitude, latitude]."
        )
        return
    lon, lat = coord[0], coord[1]
    if not isinstance(lon, (int, float)) or not isinstance(lat, (int, float)):
        errors.append(
            f"Feature {feature_index}: coordinate {coord_index} contains a non-numeric value."
        )
        return
    if not (math.isfinite(lon) and math.isfinite(lat)):
        errors.append(f"Feature {feature_index}: coordinate {coord_index} is NaN or infinite.")
        return
    if not (-180.0 <= lon <= 180.0):
        errors.append(
            f"Feature {feature_index}: longitude {lon} at coordinate {coord_index} is outside -180..180."
        )
    if not (-90.0 <= lat <= 90.0):
        errors.append(
            f"Feature {feature_index}: latitude {lat} at coordinate {coord_index} is outside -90..90."
        )


def normalize_feature_collection(raw: Any) -> tuple[dict[str, Any] | None, list[str]]:
    """
    Normalize a GeoJSON FeatureCollection / Feature / Geometry into a
    FeatureCollection and validate every coordinate. Returns (normalized,
    errors). Empty errors means valid.
    """
    errors: list[str] = []
    if not isinstance(raw, dict):
        return None, ["Payload is not a GeoJSON object."]
    rtype = raw.get("type")
    if rtype == "FeatureCollection":
        fc: dict[str, Any] = {
            "type": "FeatureCollection",
            "features": list(raw.get("features") or []),
        }
    elif rtype == "Feature":
        fc = {"type": "FeatureCollection", "features": [raw]}
    elif rtype in _GEOM_TYPES:
        fc = {
            "type": "FeatureCollection",
            "features": [{"type": "Feature", "properties": {}, "geometry": raw}],
        }
    else:
        return None, [f"Unsupported GeoJSON type: {rtype!r}."]

    features = fc.get("features") or []
    if not isinstance(features, list) or len(features) == 0:
        return None, ["FeatureCollection contains no features."]

    for i, feature in enumerate(features):
        if not isinstance(feature, dict) or feature.get("type") != "Feature":
            errors.append(f"Feature {i} is not a GeoJSON Feature.")
            continue
        geometry = feature.get("geometry")
        if geometry is None:
            errors.append(f"Feature {i} has null geometry.")
            continue
        if not isinstance(geometry, dict) or geometry.get("type") not in _GEOM_TYPES:
            errors.append(f"Feature {i} has an invalid or unsupported geometry.")
            continue
        if geometry.get("type") == "GeometryCollection":
            children = geometry.get("geometries") or []
            if not children:
                errors.append(f"Feature {i}: GeometryCollection is empty.")
                continue
        for structural in _geometry_structure_errors(geometry):
            errors.append(f"Feature {i}: {structural}")
        for coord_index, coord in enumerate(_iter_coordinates(geometry)):
            if len(errors) > 40:
                errors.append("Validation aborted after too many errors.")
                return fc, errors
            _validate_coordinate(coord, i, coord_index, errors)

    return fc, errors


def feature_collection_bounds(fc: dict[str, Any]) -> dict[str, float] | None:
    """Compute [min_lat,min_lon,max_lat,max_lon] of a validated FeatureCollection."""
    min_lat = min_lon = math.inf
    max_lat = max_lon = -math.inf
    found = False
    for feature in fc.get("features", []):
        geometry = feature.get("geometry")
        if not geometry:
            continue
        for coord in _iter_coordinates(geometry):
            lon, lat = coord[0], coord[1]
            found = True
            min_lat = min(min_lat, lat)
            max_lat = max(max_lat, lat)
            min_lon = min(min_lon, lon)
            max_lon = max(max_lon, lon)
    if not found:
        return None
    return {
        "min_lat": min_lat,
        "min_lon": min_lon,
        "max_lat": max_lat,
        "max_lon": max_lon,
    }


# ─── Service ──────────────────────────────────────────────────────────


class MapPreviewUnavailable(Exception):
    """Raised when a SAR preview cannot be produced; carries a public reason."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


class MapService:
    """Interactive map data service."""

    _preview_lock = threading.Lock()

    def __init__(self) -> None:
        # Result of the real rasterio/numpy import probe; cached per process so
        # the (potentially slow) native import runs at most once. Tests patch
        # this per instance.
        self._geo_runtime_cache: dict[str, str] = {}

    # ── Geospatial runtime capability ─────────────────────────────────

    def _geo_runtime_status(self) -> str:
        """
        Probe whether the optional numpy/rasterio runtime can really be used.

        Returns one of:
        - "available"     — both imports succeed
        - "not_installed" — packages are missing from the environment
        - "import_failed" — packages exist but the native runtime cannot be
          loaded (e.g. a Windows Application Control policy blocking a DLL)

        ``find_spec`` only proves a package is present on disk; it says nothing
        about whether native DLLs load, so this probe performs the actual import.
        Technical detail is logged server-side only — clients receive the safe
        SAR_RUNTIME_UNAVAILABLE_REASON text instead.
        """
        cached = self._geo_runtime_cache.get("status")
        if cached is not None:
            return cached
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
        self._geo_runtime_cache["status"] = status
        return status

    def _geo_runtime_available(self) -> bool:
        """True only when the real import probe reports a working runtime."""
        return self._geo_runtime_status() == "available"

    # ── Registry helpers ──────────────────────────────────────────────

    def layer_defs(self) -> list[dict[str, Any]]:
        """Registry metadata without runtime state (z-order preserved)."""
        return json.loads(json.dumps(_LAYER_DEFS))

    # ── Real-data state computation ───────────────────────────────────

    def _validated_files(self, case_id: str) -> list[dict[str, Any]]:
        files = []
        with get_db() as conn:
            rows = conn.execute(
                "SELECT * FROM files WHERE case_id = ? AND validation_status = 'validated' "
                "ORDER BY created_at",
                (case_id,),
            ).fetchall()
            for row in rows:
                d = dict(row)
                d["metadata"] = json.loads(d.get("metadata") or "{}")
                files.append(d)
        return files

    def _files_by_type(self, case_id: str) -> dict[str, list[dict[str, Any]]]:
        grouped: dict[str, list[dict[str, Any]]] = {}
        for f in self._validated_files(case_id):
            grouped.setdefault(f["file_type"], []).append(f)
        return grouped

    @staticmethod
    def _has_bbox(case: dict[str, Any]) -> bool:
        return all(
            case.get(k) is not None
            for k in ("bbox_min_lat", "bbox_min_lon", "bbox_max_lat", "bbox_max_lon")
        )

    def _compute_layer_state(
        self,
        layer_id: str,
        case: dict[str, Any],
        by_type: dict[str, list[dict[str, Any]]],
    ) -> tuple[str, str]:
        """Return (state, reason) for one layer id from genuine case state."""
        sar = by_type.get("sar", [])
        env = by_type.get("environmental", [])
        ais = by_type.get("ais", [])
        mask = by_type.get("mask", [])
        boundary = by_type.get("boundary", [])

        if layer_id == "investigation_area":
            if self._has_bbox(case):
                return "ready", ""
            return "missing_input", "No geographic bounds registered for this case."
        if layer_id == "case_boundary_dataset":
            if not boundary:
                return (
                    "missing_input",
                    "No geographic boundary GeoJSON has been registered for this case.",
                )
            state, reason, _ = self._read_boundary(boundary)
            return state, reason
        if layer_id == "coastline":
            return "unavailable", "Coastline dataset not configured in this environment."
        if layer_id == "sar_raster":
            state, reason, _status = self._sar_layer_state(case["id"], sar)
            return state, reason
        if layer_id in {
            "detection_probability",
            "detection_predicted",
            "detection_reviewed",
        }:
            if not sar:
                return (
                    "missing_input",
                    "SAR imagery required for detection has not been registered.",
                )
            return "not_processed", "Detection has not been executed."
        if layer_id == "detection_ground_truth":
            if not mask:
                return (
                    "missing_input",
                    "No ground-truth mask has been registered for this case.",
                )
            return (
                "not_processed",
                "Ground-truth mask registered; boundary extraction has not been executed.",
            )
        if layer_id.startswith("drift_"):
            if not sar:
                return (
                    "missing_input",
                    "SAR imagery required for drift simulation has not been registered.",
                )
            if not env:
                return (
                    "missing_input",
                    "Environmental wind/current data required for drift has not been registered.",
                )
            return "not_processed", "Drift simulation has not been executed."
        if layer_id in {"wind_vectors", "current_vectors", "env_coverage"}:
            if not env:
                return (
                    "missing_input",
                    "Environmental data has not been registered for this case.",
                )
            return "not_processed", "Environmental processing has not been executed."
        if layer_id.startswith("ais_"):
            if not ais:
                return (
                    "missing_input",
                    "AIS vessel dataset has not been registered for this case.",
                )
            return "not_processed", "AIS processing has not been executed."
        return "unavailable", "Layer is not supported in this environment."

    # ── Sentinel-1 SAR state machine ──────────────────────────────────
    #
    # Distinct honest states (never one generic "validated"):
    #   uploaded | format_checked | geospatial_validated | sentinel1_verified
    #   | preview_ready | processing_blocked | invalid
    #
    # A TIFF that merely matches an extension or magic bytes can never make the
    # SAR layer Ready — georeferencing must be readable and Sentinel-1
    # provenance (product identifier + source) must be present before the
    # source is treated as a verified Sentinel-1 input.

    @staticmethod
    def _sentinel_provenance(f: dict[str, Any]) -> dict[str, Any]:
        """Sentinel-1 provenance fields supplied at registration (if any)."""
        meta = f.get("metadata") or {}
        return {
            key: meta.get(key)
            for key in (
                "product_identifier",
                "acquisition_time",
                "provenance_source",
                "polarization",
            )
        }

    def _inspect_raster(self, path: str) -> dict[str, Any]:
        """
        Open a registered raster and return validated geographic metadata.

        Raises ``MapPreviewUnavailable`` with a public reason when the raster
        cannot be used as georeferenced evidence (unreadable, no CRS, invalid
        or degenerate bounds, excessive size without overviews). No pixel data
        is read here, so this is safe to run on every layer request.
        """
        import rasterio
        from rasterio import warp

        with rasterio.open(path) as src:
            if src.crs is None:
                raise MapPreviewUnavailable(
                    "Registered SAR raster does not declare a Coordinate Reference System."
                )
            epsg = src.crs.to_epsg()
            if epsg is None:
                raise MapPreviewUnavailable("Registered SAR raster CRS is not an EPSG reference.")
            if epsg == 4326:
                w, s, e, n = src.bounds
            else:
                try:
                    w, s, e, n = warp.transform_bounds(src.crs, "EPSG:4326", *src.bounds)
                except Exception as exc:  # pragma: no cover - library dependent
                    raise MapPreviewUnavailable(
                        "Registered SAR raster bounds could not be reprojected to WGS 84."
                    ) from exc
            for value in (w, s, e, n):
                if not math.isfinite(value):
                    raise MapPreviewUnavailable(
                        "Registered SAR raster has non-finite geographic bounds."
                    )
            if not (-180 <= w <= 180 and -90 <= s <= 90 and -180 <= e <= 180 and -90 <= n <= 90):
                raise MapPreviewUnavailable(
                    "Registered SAR raster bounds are outside valid WGS 84 ranges."
                )
            if w >= e or s >= n:
                raise MapPreviewUnavailable(
                    "Registered SAR raster has degenerate geographic bounds."
                )
            height, width = src.height, src.width
            overviews = src.overviews(1)
            if not overviews and height * width > 250_000_000:
                raise MapPreviewUnavailable(
                    "Registered SAR raster is very large and contains no internal "
                    "overviews; processing was declined to avoid excessive memory use."
                )
            return {
                "epsg": int(epsg),
                "bounds": (float(w), float(s), float(e), float(n)),
                "width": int(width),
                "height": int(height),
                "count": int(src.count),
                "overviews": bool(overviews),
            }

    def _sar_file_status(self, case_id: str, f: dict[str, Any]) -> tuple[str, str]:
        """
        Compute the honest SAR validation state for one registered file.

        Returns ``(status, reason)`` where status is one of the documented
        machine states. The reason is always a safe, public sentence.
        """
        if not self._geo_runtime_available():
            return "processing_blocked", SAR_RUNTIME_UNAVAILABLE_REASON

        path = f.get("file_path") or ""
        if not path or not os.path.isfile(path):
            return "invalid", "Registered SAR file is missing from local storage."

        try:
            self._inspect_raster(path)
        except MapPreviewUnavailable as exc:
            return "invalid", exc.reason
        except Exception:  # noqa: BLE001 - never expose file-system details
            return "invalid", "Registered SAR raster cannot be read as a georeferenced raster."

        # Preview already derived from this exact input checksum.
        directory = self._case_map_dir(case_id)
        sha = f.get("sha256_checksum") or ""
        meta_path = os.path.join(directory, f"sar_preview_{sha[:16]}.json")
        png_path = os.path.join(directory, f"sar_preview_{sha[:16]}.png")
        if os.path.isfile(png_path) and os.path.isfile(meta_path):
            try:
                with open(meta_path, "r", encoding="utf-8") as fh:
                    cached = json.load(fh)
                if cached.get("input_sha256") == sha:
                    return "preview_ready", ""
            except (OSError, ValueError):
                pass

        provenance = self._sentinel_provenance(f)
        if provenance.get("product_identifier") and provenance.get("provenance_source"):
            return (
                "sentinel1_verified",
                (
                    "Sentinel-1 source verified (derived GeoTIFF, provenance recorded); "
                    "preview generation required."
                ),
            )
        if provenance.get("product_identifier") or provenance.get("provenance_source"):
            return (
                "geospatial_validated",
                (
                    "Geospatial raster verified; Sentinel-1 provenance incomplete "
                    "(product identifier and source are both required)."
                ),
            )
        return (
            "geospatial_validated",
            "Geospatial raster verified; Sentinel-1 provenance incomplete.",
        )

    def _sar_layer_state(
        self, case_id: str, sar_files: list[dict[str, Any]]
    ) -> tuple[str, str, str | None]:
        """
        Map the SAR file state machine onto the typed layer registry.

        Returns ``(layer_state, reason, validation_status)``. An arbitrary TIFF
        can never reach ``ready``: it must be a readable georeferenced raster
        whose preview has been derived from the exact registered checksum.
        """
        if not sar_files:
            return (
                "missing_input",
                "SAR imagery (Sentinel-1 GeoTIFF) has not been registered.",
                None,
            )
        status, reason = self._sar_file_status(case_id, sar_files[-1])
        if status == "processing_blocked":
            return "unavailable", reason, status
        if status == "invalid":
            return "failed", reason, status
        if status == "preview_ready":
            return "ready", "", status
        return "not_processed", reason, status

    # ── Boundary GeoJSON ──────────────────────────────────────────────

    def _read_boundary(
        self, boundary_files: list[dict[str, Any]]
    ) -> tuple[str, str, dict[str, Any] | None]:
        """Read and validate the most recently registered boundary file."""
        if not boundary_files:
            return (
                "missing_input",
                "No geographic boundary GeoJSON has been registered for this case.",
                None,
            )
        f = boundary_files[-1]
        path = f.get("file_path") or ""
        if not path or not os.path.isfile(path):
            return "failed", "Registered boundary file is missing from local storage.", None
        try:
            size = os.path.getsize(path)
            if size > 100 * 1024 * 1024:
                return "failed", "Registered boundary file exceeds the 100 MB read limit.", None
            with open(path, "r", encoding="utf-8") as fh:
                raw = json.load(fh)
        except (OSError, ValueError, UnicodeDecodeError):
            return "failed", "Registered boundary file is not valid GeoJSON.", None
        fc, errors = normalize_feature_collection(raw)
        if fc is None or errors:
            preview = "; ".join(errors[:2])
            return "failed", f"Registered boundary file contains invalid geometry. {preview}", None
        return "ready", "", fc

    @staticmethod
    def _build_investigation_area(case: dict[str, Any]) -> dict[str, Any]:
        """Build the investigation-area FeatureCollection from real case bounds."""
        min_lon = case["bbox_min_lon"]
        min_lat = case["bbox_min_lat"]
        max_lon = case["bbox_max_lon"]
        max_lat = case["bbox_max_lat"]
        ring = [
            [min_lon, min_lat],
            [max_lon, min_lat],
            [max_lon, max_lat],
            [min_lon, max_lat],
            [min_lon, min_lat],
        ]
        return {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "id": f"{case['id']}-area",
                    "properties": {
                        "layer": "investigation_area",
                        "title": case.get("title", ""),
                        "source": "case_bounding_box",
                        "crs": "EPSG:4326",
                    },
                    "geometry": {"type": "Polygon", "coordinates": [ring]},
                }
            ],
        }

    # ── Public map endpoints data ─────────────────────────────────────

    def get_case_or_404(self, case_id: str) -> dict[str, Any] | None:
        return case_service.get_case(case_id)

    def build_layers(self, case: dict[str, Any]) -> list[dict[str, Any]]:
        """Layer metadata with honest runtime state for a case."""
        by_type = self._files_by_type(case["id"])
        layers: list[dict[str, Any]] = []
        for definition in _LAYER_DEFS:
            layer_id = definition["id"]
            state, reason = self._compute_layer_state(layer_id, case, by_type)
            info = json.loads(json.dumps(definition))
            info["state"] = state
            info["reason"] = reason
            info["crs"] = "EPSG:4326"
            info["timestamps"] = None
            info["validation_status"] = None
            if layer_id == "sar_raster":
                _, _, validation_status = self._sar_layer_state(case["id"], by_type.get("sar", []))
                info["validation_status"] = validation_status
            layers.append(info)
        return layers

    def build_summary(self, case: dict[str, Any]) -> dict[str, Any]:
        """Map-readiness summary computed from genuine case + file state."""
        layers = self.build_layers(case)
        by_type = self._files_by_type(case["id"])
        ready = [layer for layer in layers if layer["state"] == "ready"]
        pending = [layer for layer in layers if layer["state"] in {"processing", "awaiting_review"}]
        unavailable = [
            layer
            for layer in layers
            if layer["state"] not in {"ready", "processing", "awaiting_review"}
        ]

        bounds = None
        if self._has_bbox(case):
            bounds = {
                "min_lat": case["bbox_min_lat"],
                "min_lon": case["bbox_min_lon"],
                "max_lat": case["bbox_max_lat"],
                "max_lon": case["bbox_max_lon"],
            }

        # Time range from genuine case timestamps.
        time_range = None
        times = [case.get("incident_time"), case.get("observation_time")]
        times = [t for t in times if t]
        if times:
            time_range = {"start": min(times), "end": max(times)}

        has_geospatial = bool(bounds) or bool(by_type.get("boundary")) or bool(by_type.get("sar"))

        all_files = self._validated_files(case["id"])
        if not all_files:
            integrity = "no_data"
        elif all(f.get("validation_status") == "validated" for f in all_files):
            integrity = "ok"
        else:
            integrity = "warning"

        reasons = []
        seen = set()
        for layer in unavailable:
            if layer["reason"] and layer["reason"] not in seen:
                seen.add(layer["reason"])
                reasons.append(layer["reason"])

        return {
            "case_id": case["id"],
            "case_title": case.get("title", ""),
            "region": case.get("region", ""),
            "status": case.get("status", ""),
            "current_stage": case.get("current_stage", ""),
            "bounds": bounds,
            "time_range": time_range,
            "available_layer_ids": [layer["id"] for layer in ready],
            "pending_layer_ids": [layer["id"] for layer in pending],
            "unavailable_layer_ids": [layer["id"] for layer in unavailable],
            "missing_data": reasons,
            "has_geospatial_data": has_geospatial,
            "map_ready": has_geospatial,
            "data_integrity": integrity,
            "registered_files": {
                file_type: len(files) for file_type, files in sorted(by_type.items())
            },
        }

    def build_features(
        self, case: dict[str, Any], requested: list[str] | None = None
    ) -> dict[str, dict[str, Any]]:
        """
        Feature payload per requested vector layer. Layers with no real data
        return a typed non-ready state with reason and null features - never an
        empty, misleading success.
        """
        by_type = self._files_by_type(case["id"])
        ids = requested or sorted(_VECTOR_LAYER_IDS)
        invalid = [i for i in ids if i not in _VECTOR_LAYER_IDS]
        if invalid:
            raise ValueError(f"Unknown vector layer id(s): {', '.join(invalid)}")

        result: dict[str, dict[str, Any]] = {}
        generated_at = datetime.now(UTC).isoformat()
        for layer_id in ids:
            state, reason = self._compute_layer_state(layer_id, case, by_type)
            features = None
            if layer_id == "investigation_area" and state == "ready":
                features = self._build_investigation_area(case)
            elif layer_id == "case_boundary_dataset":
                b_state, b_reason, fc = self._read_boundary(by_type.get("boundary", []))
                state, reason = b_state, b_reason
                features = fc
            result[layer_id] = {
                "layer": layer_id,
                "state": state,
                "reason": reason,
                "features": features,
                "timestamps": None,
                "crs": "EPSG:4326",
                "generated_at": generated_at,
            }
        return result

    # ── SAR preview ───────────────────────────────────────────────────

    def _case_map_dir(self, case_id: str) -> str:
        base = os.path.join(config.settings.DATA_DIR, "cases", case_id, "map")
        os.makedirs(base, exist_ok=True)
        return base

    def get_sar_overlay(self, case_id: str) -> dict[str, Any]:
        """
        Describe the derived SAR preview overlay for a case. When a preview
        cannot be produced (no library, corrupt raster, unsupported CRS, ...)
        the response is honestly marked unavailable with a public reason.
        """
        sar_files = self._validated_files(case_id)
        sar = [f for f in sar_files if f["file_type"] == "sar"]
        if not sar:
            return {
                "available": False,
                "state": "missing_input",
                "reason": "SAR imagery (Sentinel-1 GeoTIFF) has not been registered.",
                "validation_status": None,
                "file_id": None,
                "url": None,
            }
        f = sar[-1]
        validation_status, status_reason = self._sar_file_status(case_id, f)

        if validation_status in ("processing_blocked", "invalid"):
            return {
                "available": False,
                "state": "failed" if validation_status == "invalid" else "unavailable",
                "reason": status_reason,
                "validation_status": validation_status,
                "file_id": f["id"],
                "url": None,
            }
        if validation_status != "preview_ready":
            return {
                "available": False,
                "state": "not_processed",
                "reason": status_reason,
                "validation_status": validation_status,
                "file_id": f["id"],
                "url": None,
            }

        meta = self._ensure_sar_preview(case_id, f)
        if meta is None:
            # Preview generation is unavailable/failed; inspect the reason.
            reason = self._sar_preview_failure_reason(case_id, f)
            return {
                "available": False,
                "state": "unavailable",
                "reason": reason,
                "validation_status": validation_status,
                "file_id": f["id"],
                "url": None,
            }
        provenance = self._sentinel_provenance(f)
        png_name = f"sar_preview_{f['sha256_checksum'][:16]}.png"
        return {
            "available": True,
            "state": "ready",
            "reason": "",
            "validation_status": validation_status,
            "file_id": f["id"],
            "source_filename": f["original_filename"],
            "url": f"/api/cases/{case_id}/map/sar-preview/{f['id']}",
            "png_name": png_name,
            "bounds": meta["bounds"],  # [west, south, east, north]
            "crs": "EPSG:4326",
            "width": meta["width"],
            "height": meta["height"],
            "band": 1,
            "input_sha256": f["sha256_checksum"],
            "preview_sha256": meta["preview_sha256"],
            "generated_at": meta["generated_at"],
            "config": meta["config"],
            "acquisition_time": provenance.get("acquisition_time") or None,
            "polarisation": provenance.get("polarization") or None,
            "product_identifier": provenance.get("product_identifier") or None,
            "provenance_source": provenance.get("provenance_source") or None,
        }

    def _sar_preview_failure_reason(self, case_id: str, f: dict[str, Any]) -> str:
        """Return the recorded or computed failure reason for a SAR file."""
        if not self._geo_runtime_available():
            return SAR_RUNTIME_UNAVAILABLE_REASON
        status, reason = self._sar_file_status(case_id, f)
        if status in ("invalid", "processing_blocked"):
            return reason
        return "SAR preview generation failed for the registered raster."

    def _ensure_sar_preview(self, case_id: str, f: dict[str, Any]) -> dict[str, Any] | None:
        """Create (or reuse) the derived SAR preview; returns metadata or None."""
        sha = f.get("sha256_checksum") or ""
        prefix = sha[:16]
        directory = self._case_map_dir(case_id)
        meta_path = os.path.join(directory, f"sar_preview_{prefix}.json")
        png_path = os.path.join(directory, f"sar_preview_{prefix}.png")

        # Cache hit: input checksum must still match.
        if os.path.isfile(png_path) and os.path.isfile(meta_path):
            try:
                with open(meta_path, "r", encoding="utf-8") as fh:
                    meta = json.load(fh)
                if meta.get("input_sha256") == sha:
                    return meta
            except (OSError, ValueError):
                pass

        if not self._geo_runtime_available():
            return None

        with self._preview_lock:
            # Re-check inside the lock (another request may have generated it).
            if os.path.isfile(png_path) and os.path.isfile(meta_path):
                try:
                    with open(meta_path, "r", encoding="utf-8") as fh:
                        meta = json.load(fh)
                    if meta.get("input_sha256") == sha:
                        return meta
                except (OSError, ValueError):
                    pass

            path = f.get("file_path") or ""
            if not path or not os.path.isfile(path):
                return None
            try:
                meta = self._generate_sar_preview(path, png_path, sha)
            except MapPreviewUnavailable:
                return None
            except Exception:  # noqa: BLE001 - never leak file-system details
                return None
            meta["case_id"] = case_id
            meta["file_id"] = f["id"]
            meta["source_filename"] = f["original_filename"]
            meta["input_sha256"] = sha
            try:
                with open(meta_path, "w", encoding="utf-8") as fh:
                    json.dump(meta, fh)
            except OSError:
                return None
            return meta

    def _generate_sar_preview(self, path: str, out_png: str, input_sha: str) -> dict[str, Any]:
        """Derive a grayscale PNG preview from a real georeferenced raster."""
        import numpy as np
        import rasterio

        inspected = self._inspect_raster(path)
        w, s, e, n = inspected["bounds"]
        target = 2048
        scale = min(1.0, target / max(inspected["height"], inspected["width"]))
        out_h = max(1, round(inspected["height"] * scale))
        out_w = max(1, round(inspected["width"] * scale))
        with rasterio.open(path) as src:
            data = src.read(1, out_shape=(out_h, out_w))

        array = np.asarray(data)
        if array.ndim != 2:
            raise MapPreviewUnavailable("SAR raster band is not two-dimensional.")
        if array.dtype == bool:
            grey = array.astype(np.uint8) * 255
        elif np.issubdtype(array.dtype, np.floating):
            finite = array[np.isfinite(array)]
            if finite.size == 0:
                raise MapPreviewUnavailable("SAR raster band contains no finite values to render.")
            p2 = float(np.percentile(finite, 2))
            p98 = float(np.percentile(finite, 98))
            span = (p98 - p2) or 1.0
            clipped = np.clip(array, p2, p98)
            grey = ((clipped - p2) / span * 255.0).astype(np.uint8)
        else:
            # Integer DN: robust percentile stretch without fabricating values.
            finite = array.astype(np.float64)
            p2 = float(np.percentile(finite, 2))
            p98 = float(np.percentile(finite, 98))
            span = (p98 - p2) or 1.0
            clipped = np.clip(array.astype(np.float64), p2, p98)
            grey = ((clipped - p2) / span * 255.0).astype(np.uint8)

        grey = np.ascontiguousarray(grey)
        self._write_grayscale_png(out_png, grey)
        preview_sha = FileService.compute_sha256(out_png)

        generated_at = datetime.now(UTC).isoformat()
        meta: dict[str, Any] = {
            "derived_from": "sar_raster_preview",
            "input_sha256": input_sha,
            "preview_sha256": preview_sha,
            "output_filename": os.path.basename(out_png),
            "generated_at": generated_at,
            "bounds": [float(w), float(s), float(e), float(n)],
            "crs_out": "EPSG:4326",
            "width": int(grey.shape[1]),
            "height": int(grey.shape[0]),
            "band": 1,
            "config": {
                "max_dimension": target,
                "stretch": "percentile_2_98",
                "colour": "grayscale",
                "format": "png",
                "overview_used": inspected["overviews"],
            },
        }
        return meta

    @staticmethod
    def _write_grayscale_png(path: str, arr) -> None:
        """Write an 8-bit grayscale PNG using only the standard library."""
        height, width = arr.shape
        raw = bytearray()
        for row in arr:
            raw.append(0)  # filter type: none
            raw.extend(row.tobytes())

        def chunk(tag: bytes, payload: bytes) -> bytes:
            return (
                struct.pack(">I", len(payload))
                + tag
                + payload
                + struct.pack(">I", zlib.crc32(tag + payload) & 0xFFFFFFFF)
            )

        signature = b"\x89PNG\r\n\x1a\n"
        ihdr = struct.pack(">IIBBBBB", width, height, 8, 0, 0, 0, 0)
        idat = zlib.compress(bytes(raw), 9)
        with open(path, "wb") as fh:
            fh.write(signature)
            fh.write(chunk(b"IHDR", ihdr))
            fh.write(chunk(b"IDAT", idat))
            fh.write(chunk(b"IEND", b""))

    def read_sar_preview_bytes(self, case_id: str, file_id: str) -> tuple[bytes | None, str]:
        """Read cached preview PNG bytes for a SAR file. Returns (bytes, reason)."""
        f = self._get_sar_file(case_id, file_id)
        if f is None:
            return None, "File not found in this case."
        directory = self._case_map_dir(case_id)
        prefix = f["sha256_checksum"][:16]
        png_path = os.path.join(directory, f"sar_preview_{prefix}.png")
        if not os.path.isfile(png_path):
            meta = self._ensure_sar_preview(case_id, f)
            if meta is None:
                return None, self._sar_preview_failure_reason(case_id, f)
        try:
            with open(png_path, "rb") as fh:
                return fh.read(), ""
        except OSError:
            return None, "Preview file could not be read."

    def _get_sar_file(self, case_id: str, file_id: str) -> dict[str, Any] | None:
        for f in self._validated_files(case_id):
            if f["id"] == file_id and f["file_type"] == "sar":
                return f
        return None

    # ── Provenance ────────────────────────────────────────────────────

    def build_provenance(self, case_id: str) -> dict[str, Any]:
        """Source dataset + derived artifact provenance (no filesystem paths)."""
        sources = []
        for f in self._validated_files(case_id):
            provenance = self._sentinel_provenance(f)
            sar_status = None
            if f["file_type"] == "sar":
                sar_status, _ = self._sar_file_status(case_id, f)
            source = {
                "file_id": f["id"],
                "file_type": f["file_type"],
                "original_filename": f["original_filename"],
                "file_size": f["file_size"],
                "mime_type": f["mime_type"],
                "sha256_checksum": f["sha256_checksum"],
                "validation_status": f["validation_status"],
                "registered_at": f["created_at"],
                "crs": None,
                "bounds": None,
            }
            if f["file_type"] == "sar":
                source["sar_validation_status"] = sar_status
                source["product_identifier"] = provenance.get("product_identifier")
                source["acquisition_time"] = provenance.get("acquisition_time")
                source["provenance_source"] = provenance.get("provenance_source")
                source["polarization"] = provenance.get("polarization")
            sources.append(source)

        derived = []
        directory = self._case_map_dir(case_id)
        try:
            entries = os.listdir(directory)
        except OSError:
            entries = []
        for name in sorted(entries):
            if not name.startswith("sar_preview_") or not name.endswith(".json"):
                continue
            try:
                with open(os.path.join(directory, name), "r", encoding="utf-8") as fh:
                    meta = json.load(fh)
            except (OSError, ValueError):
                continue
            derived.append(
                {
                    "artifact": "sar_grayscale_preview",
                    "file_id": meta.get("file_id"),
                    "source_filename": meta.get("source_filename"),
                    "input_sha256": meta.get("input_sha256"),
                    "sha256_checksum": meta.get("preview_sha256"),
                    "generated_at": meta.get("generated_at"),
                    "bounds_wsen": meta.get("bounds"),
                    "width": meta.get("width"),
                    "height": meta.get("height"),
                    "config": meta.get("config"),
                    "derived_from": meta.get("derived_from"),
                }
            )

        return {
            "case_id": case_id,
            "sources": sources,
            "derived_artifacts": derived,
            "note": (
                "Every derived artifact records its input checksum and generation "
                "configuration; cache entries whose input checksum no longer matches "
                "are regenerated before use."
            ),
        }

    # ── Viewport persistence ──────────────────────────────────────────

    def get_viewport(self, case_id: str) -> dict[str, Any]:
        """Current saved viewport (or null) plus a data-derived default viewport."""
        with get_db() as conn:
            row = conn.execute(
                "SELECT center_lon, center_lat, zoom, bearing, pitch FROM map_viewports "
                "WHERE case_id = ?",
                (case_id,),
            ).fetchone()
        saved = None
        if row is not None:
            saved = {
                "center_lon": row["center_lon"],
                "center_lat": row["center_lat"],
                "zoom": row["zoom"],
                "bearing": row["bearing"],
                "pitch": row["pitch"],
            }

        case = case_service.get_case(case_id)
        default = None
        bounds = None
        if case and self._has_bbox(case):
            bounds = {
                "min_lat": case["bbox_min_lat"],
                "min_lon": case["bbox_min_lon"],
                "max_lat": case["bbox_max_lat"],
                "max_lon": case["bbox_max_lon"],
            }
            center_lat = (bounds["min_lat"] + bounds["max_lat"]) / 2.0
            center_lon = (bounds["min_lon"] + bounds["max_lon"]) / 2.0
            lon_span = max(1e-6, bounds["max_lon"] - bounds["min_lon"])
            lat_span = max(1e-6, bounds["max_lat"] - bounds["min_lat"])
            span = max(lon_span, lat_span)
            zoom = max(2.0, min(13.0, math.log2(360.0 / span)))
            default = {
                "center_lon": round(center_lon, 6),
                "center_lat": round(center_lat, 6),
                "zoom": round(zoom, 2),
                "bearing": 0.0,
                "pitch": 0.0,
            }
        return {
            "case_id": case_id,
            "viewport": saved,
            "default_viewport": default,
            "bounds": bounds,
        }

    def save_viewport(self, case_id: str, viewport: dict[str, Any]) -> dict[str, Any]:
        """Persist a safe analyst viewport preference."""
        now = datetime.now(UTC).isoformat()
        with get_db() as conn:
            conn.execute(
                "INSERT INTO map_viewports (case_id, center_lon, center_lat, zoom, "
                "bearing, pitch, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(case_id) DO UPDATE SET center_lon = excluded.center_lon, "
                "center_lat = excluded.center_lat, zoom = excluded.zoom, "
                "bearing = excluded.bearing, pitch = excluded.pitch, "
                "updated_at = excluded.updated_at",
                (
                    case_id,
                    viewport["center_lon"],
                    viewport["center_lat"],
                    viewport["zoom"],
                    viewport.get("bearing", 0.0),
                    viewport.get("pitch", 0.0),
                    now,
                ),
            )
        return {"case_id": case_id, "viewport": viewport, "updated_at": now}


map_service = MapService()
