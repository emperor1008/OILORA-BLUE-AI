"""
Oilora Blue AI — Shared Validation Helpers

Pure validation logic shared by the Pydantic case models, the case service,
and the file upload router. No framework dependencies here so the rules are
unit-testable in isolation.

Timestamp policy
----------------
- Timestamps must be timezone-aware ISO 8601 values.
- Stored values are normalized to canonical UTC (``YYYY-MM-DDTHH:MM:SS.mmmZ``)
  so string ordering and the map timeline remain consistent.
- Naive timestamps are rejected (ambiguous); past observations are allowed.
- Future timestamps are rejected beyond a small tolerance because no
  scheduling workflow is documented in this application.

Bounding-box policy
-------------------
- All four corners must be supplied together, be finite, within WGS 84
  ranges, and describe a non-degenerate area (min < max on both axes).
"""

from __future__ import annotations

import math
from datetime import UTC, datetime, timedelta
from typing import Any

# No documented scheduling workflow exists; tolerate small clock skew only.
FUTURE_SKEW_TOLERANCE = timedelta(hours=24)

BBOX_KEYS = ("bbox_min_lat", "bbox_min_lon", "bbox_max_lat", "bbox_max_lon")


def normalize_iso_utc(value: str | None) -> str | None:
    """
    Parse an ISO 8601 timestamp and return canonical UTC ``...Z`` form.

    Raises ``ValueError`` with a user-facing message for invalid or naive
    (timezone-less) values; empty strings and None are treated as missing.
    """
    if value is None or (isinstance(value, str) and value.strip() == ""):
        return None
    if not isinstance(value, str):
        # Pydantic field validators surface ValueError as a 422; TypeError
        # would escape as a server error, so ValueError is intentional here.
        raise ValueError("must be an ISO 8601 timestamp string")  # noqa: TRY004
    parsed = parse_iso_utc(value)
    return parsed.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def parse_iso_utc(value: str) -> datetime:
    """
    Parse an ISO 8601 timestamp; returns a timezone-aware ``datetime``.

    Raises ``ValueError`` with a user-facing message when the value cannot be
    parsed or carries no timezone information.
    """
    if not isinstance(value, str):
        # See normalize_iso_utc: ValueError is required for Pydantic 422s.
        raise ValueError("must be an ISO 8601 timestamp string")  # noqa: TRY004
    try:
        # Python 3.11+ accepts a trailing 'Z' in fromisoformat.
        parsed = datetime.fromisoformat(value)
    except ValueError:
        raise ValueError("must be a valid ISO 8601 timestamp (e.g. 2024-01-15T10:30:00Z)") from None
    if parsed.tzinfo is None:
        raise ValueError("must include a timezone (e.g. 'Z' or '+00:00')")
    return parsed


def validate_case_semantics(data: dict[str, Any]) -> list[dict[str, str]]:
    """
    Validate cross-field case semantics (chronology, bounds) after per-field
    parsing. Returns a list of ``{"loc": [...], "msg": ...}`` entries shaped
    like FastAPI's 422 detail so the frontend can render field-level errors.
    """
    errors: list[dict[str, str]] = []

    # ── Geographic bounds ──────────────────────────────────────────────
    present = [key for key in BBOX_KEYS if data.get(key) is not None]
    if present and len(present) != 4:
        errors.append(
            {
                "loc": ["body", "bbox"],
                "msg": "All four bounding-box coordinates must be provided together.",
            }
        )
    elif len(present) == 4:
        values = {key: data.get(key) for key in BBOX_KEYS}
        for key, value in values.items():
            if value is None:
                continue
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                errors.append({"loc": ["body", key], "msg": "must be a number"})
            elif not math.isfinite(float(value)):
                errors.append({"loc": ["body", key], "msg": "must be a finite number"})
        try:
            min_lat, min_lon = float(values["bbox_min_lat"]), float(values["bbox_min_lon"])
            max_lat, max_lon = float(values["bbox_max_lat"]), float(values["bbox_max_lon"])
        except (TypeError, ValueError):
            min_lat = min_lon = max_lat = max_lon = None
        if None not in (min_lat, min_lon, max_lat, max_lon):
            if min_lat >= max_lat:
                errors.append(
                    {
                        "loc": ["body", "bbox_min_lat"],
                        "msg": "Minimum latitude must be less than maximum latitude.",
                    }
                )
            if min_lon >= max_lon:
                errors.append(
                    {
                        "loc": ["body", "bbox_min_lon"],
                        "msg": "Minimum longitude must be less than maximum longitude.",
                    }
                )

    # ── Chronology ─────────────────────────────────────────────────────
    incident = data.get("incident_time")
    observation = data.get("observation_time")
    incident_dt = observation_dt = None
    for key, holder in (("incident_time", incident), ("observation_time", observation)):
        if holder:
            try:
                if key == "incident_time":
                    incident_dt = parse_iso_utc(holder)
                else:
                    observation_dt = parse_iso_utc(holder)
            except ValueError:
                # Per-field parsing already reported a 422; do not duplicate.
                pass
    if incident_dt is not None and observation_dt is not None and incident_dt > observation_dt:
        errors.append(
            {
                "loc": ["body", "incident_time"],
                "msg": "Incident time must not be after observation time "
                "(the spill occurrence precedes the satellite observation).",
            }
        )

    # ── Unreasonably-future timestamps ─────────────────────────────────
    now = datetime.now(UTC)
    for key in ("incident_time", "observation_time"):
        value = data.get(key)
        if not value:
            continue
        try:
            parsed = parse_iso_utc(value)
        except ValueError:
            continue
        if parsed > now + FUTURE_SKEW_TOLERANCE:
            errors.append(
                {
                    "loc": ["body", key],
                    "msg": "Timestamp is unreasonably far in the future for this "
                    "application (no scheduling workflow is documented).",
                }
            )

    return errors
