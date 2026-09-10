"""
Oilora Blue AI — Historical Incident Service

Source-registered reference records for historical exploration. Kept fully
separate from user-created investigations (cases).

Design rules
------------
* Every important field carries provenance (historical_incident_field_sources).
* Source records are never treated as independently scientifically verified;
  verification_status stays ``source_imported`` unless a curator upgrades it.
* Missing values stay missing (NULL) — never zero, never a guessed default.
* Imports are repeatable and idempotent (UNIQUE source_id + source_record_id).
* Satellite catalogue matches are metadata-only observations.
"""

from __future__ import annotations

import csv
import io
import json
import logging
import math
import re
import uuid
from datetime import UTC, date, datetime, timedelta
from typing import Any

from fastapi import HTTPException

from ..database import get_db
from .historical_locations import derive_country, state_from_us_text

logger = logging.getLogger("oilora_blue.historical")

NOAA_SOURCE_ID = "noaa_incidentnews"
NOAA_ORGANIZATION = "NOAA Office of Response and Restoration"
NOAA_DATASET = "IncidentNews"
NOAA_DOCUMENTATION_URL = "https://incidentnews.noaa.gov/"
NOAA_LIMITATION = (
    "NOAA IncidentNews contains selected oil and chemical incidents, largely "
    "where NOAA provided scientific support. It is not a complete worldwide "
    "oil-spill database, may include non-oil incidents, and some records have "
    "incomplete locations or fields. Records are source-registered historical "
    "reports, not independent scientific verification."
)


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


def _parse_float(text: str | None) -> float | None:
    if text is None:
        return None
    cleaned = text.strip().replace(",", "")
    if cleaned == "":
        return None
    try:
        value = float(cleaned)
    except ValueError:
        return None
    if not math.isfinite(value):
        return None
    return value


def _parse_date_utc(text: str | None) -> tuple[str | None, str]:
    """Parse a calendar date (YYYY-MM-DD) into UTC midnight.

    Returns (start_time_utc, time_precision). NOAA open_date is a calendar
    date; noon UTC is avoided so day-precision stays unambiguous when
    displayed. We normalize to 00:00:00Z.
    """
    if text is None or not text.strip():
        return None, "unknown"
    value = text.strip()
    match = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", value)
    if match:
        try:
            date(int(match[1]), int(match[2]), int(match[3]))
        except ValueError:
            return None, "unknown"
        return f"{value}T00:00:00Z", "day"
    match = re.fullmatch(r"(\d{4})-(\d{2})", value)
    if match:
        try:
            date(int(match[1]), int(match[2]), 1)
        except ValueError:
            return None, "unknown"
        return f"{value}-01T00:00:00Z", "month"
    match = re.fullmatch(r"(\d{4})", value)
    if match:
        return f"{value}-01-01T00:00:00Z", "year"
    return None, "unknown"


# ─── NOAA IncidentNews CSV import ─────────────────────────────────────

NOAA_CSV_FIELDS = [
    "id",
    "open_date",
    "name",
    "location",
    "lat",
    "lon",
    "threat",
    "tags",
    "commodity",
    "measure_skim",
    "measure_shore",
    "measure_bio",
    "measure_disperse",
    "measure_burn",
    "max_ptl_release_gallons",
    "posts",
    "description",
]


def _normalize_noaa_row(row: dict[str, Any]) -> dict[str, Any]:
    """Normalize one raw NOAA CSV row into a provenance-bearing record.

    Missing values remain None. Rows that fail hard validation collect
    rejection reasons instead of being imported.
    """
    source_record_id = (row.get("id") or "").strip()
    name = (row.get("name") or "").strip()
    location = (row.get("location") or "").strip()
    summary = (row.get("description") or "").strip()
    commodity = (row.get("commodity") or "").strip() or None
    threat = (row.get("threat") or "").strip() or None
    raw_lat = (row.get("lat") or "").strip()
    raw_lon = (row.get("lon") or "").strip()

    rejections: list[str] = []
    if not source_record_id:
        rejections.append("missing source record id")
    if not name:
        rejections.append("missing incident name")

    start_time_utc, time_precision = _parse_date_utc((row.get("open_date") or "").strip())
    if start_time_utc is None:
        rejections.append("invalid or missing open date")

    latitude = _parse_float(raw_lat) if raw_lat else None
    longitude = _parse_float(raw_lon) if raw_lon else None
    if latitude is not None and not (-90.0 <= latitude <= 90.0):
        rejections.append(f"latitude {latitude} outside [-90, 90]")
        latitude = None
    if longitude is not None and not (-180.0 <= longitude <= 180.0):
        rejections.append(f"longitude {longitude} outside [-180, 180]")
        longitude = None
    if latitude is None and longitude is not None:
        rejections.append("longitude present without latitude")
        longitude = None
    if longitude is None and latitude is not None:
        rejections.append("latitude present without longitude")
        latitude = None

    # NOAA "threat" values are Oil / Chemical / Other; blank means the source
    # did not categorize it — preserved as "Unspecified" for filtering while
    # the original blank is kept in the payload and field provenance.
    category = threat if threat in ("Oil", "Chemical", "Other") else "Unspecified"

    quantity = _parse_float(row.get("max_ptl_release_gallons"))
    quantity_status = None
    quantity_unit = None
    if quantity is not None:
        quantity_unit = "US gallons"
        quantity_status = "maximum potential release reported by source"

    country = derive_country(location)
    state = state_from_us_text(location)

    payload = {key: row.get(key) for key in NOAA_CSV_FIELDS if key in row}

    return {
        "source_record_id": source_record_id,
        "canonical_name": name,
        "incident_category": category,
        "start_time_utc": start_time_utc,
        "time_precision": time_precision,
        "latitude": latitude,
        "longitude": longitude,
        "location_description": location or None,
        "country": country,
        "state": state,
        "substance_name": commodity,
        "substance_category": "Oil" if (threat == "Oil" and commodity) else None,
        "quantity_max": quantity,
        "quantity_unit": quantity_unit,
        "quantity_status": quantity_status,
        "summary": summary or None,
        "original_payload": payload,
        "rejections": rejections,
    }


def _noaa_source_url(record_id: str) -> str:
    return f"https://incidentnews.noaa.gov/incident/{record_id}"


class HistoricalIncidentService:
    """Persistence and query layer for historical incidents."""

    # ── Import ─────────────────────────────────────────────────────────

    def import_noaa_csv(
        self,
        content: bytes,
        source_url: str,
        retrieved_at: str | None = None,
        limit: int | None = None,
    ) -> dict[str, Any]:
        """Import the NOAA IncidentNews raw CSV. Repeatable and idempotent."""
        import hashlib

        checksum = hashlib.sha256(content).hexdigest()
        started = _now_iso()
        run_id: int | None = None

        # Parse defensively; a row that is too damaged to decode is rejected.
        raw_rows: list[dict[str, Any]] = []
        parse_errors = 0
        try:
            text = content.decode("utf-8-sig", errors="replace")
            raw_rows = list(csv.DictReader(io.StringIO(text)))
        except Exception as exc:  # noqa: BLE001 - defensive CSV parse
            logger.warning("NOAA CSV parse aborted: %s", exc)
            parse_errors += 1

        if limit is not None and limit > 0:
            raw_rows = raw_rows[:limit]

        normalized: list[dict[str, Any]] = []
        rejected: list[dict[str, Any]] = []
        for row in raw_rows:
            record = _normalize_noaa_row(row)
            if record["rejections"]:
                rejected.append(
                    {
                        "source_record_id": record["source_record_id"] or "unknown",
                        "name": record["canonical_name"] or "unnamed",
                        "reasons": record["rejections"],
                    }
                )
            else:
                normalized.append(record)

        with get_db() as conn:
            cursor = conn.execute(
                """INSERT INTO historical_incident_import_runs
                   (source_name, source_url, source_version_or_retrieval_date,
                    started_at, source_checksum, import_status)
                   VALUES (?, ?, ?, ?, ?, 'running')""",
                (NOAA_DATASET, source_url, retrieved_at, started, checksum),
            )
            run_id = int(cursor.lastrowid)

        created = 0
        updated = 0
        for record in normalized:
            outcome = self._upsert_noaa_record(record)
            created += 1 if outcome == "created" else 0
            updated += 1 if outcome == "updated" else 0

        completed = _now_iso()
        with get_db() as conn:
            conn.execute(
                """UPDATE historical_incident_import_runs SET
                   completed_at = ?, records_received = ?, records_created = ?,
                   records_updated = ?, records_rejected = ?,
                   rejection_report = ?, import_status = 'completed'
                   WHERE id = ?""",
                (
                    completed,
                    len(raw_rows),
                    created,
                    updated,
                    len(rejected) + parse_errors,
                    json.dumps(rejected),
                    run_id,
                ),
            )

        return {
            "import_run_id": run_id,
            "source_name": NOAA_DATASET,
            "source_url": source_url,
            "retrieved_at": retrieved_at,
            "records_received": len(raw_rows),
            "records_created": created,
            "records_updated": updated,
            "records_rejected": len(rejected) + parse_errors,
            "rejection_report": rejected,
            "source_checksum": checksum,
            "status": "completed",
        }

    def _upsert_noaa_record(self, record: dict[str, Any]) -> str:
        """Insert or update one normalized NOAA record plus provenance."""
        now = _now_iso()
        incident_id = f"inc-{uuid.uuid4().hex[:12]}"
        source_row_id = f"src-{uuid.uuid4().hex[:12]}"
        start_time = record["start_time_utc"]
        # End time is the same day for day-precision NOAA records.
        end_time = None
        if start_time and record["time_precision"] == "day":
            dt = datetime.fromisoformat(start_time)
            end_time = (dt + timedelta(days=1)).isoformat()

        with get_db() as conn:
            existing = conn.execute(
                "SELECT id FROM historical_incidents WHERE source_id = ? AND source_record_id = ?",
                (NOAA_SOURCE_ID, record["source_record_id"]),
            ).fetchone()
            if existing:
                incident_id = existing["id"]
                conn.execute(
                    """UPDATE historical_incidents SET
                       canonical_name = ?, incident_category = ?,
                       verification_status = 'source_imported',
                       start_time_utc = ?, end_time_utc = ?, time_precision = ?,
                       country = ?, location_description = ?, latitude = ?,
                       longitude = ?, coordinate_accuracy = ?, location_method = ?,
                       substance_name = ?, substance_category = ?,
                       quantity_max = ?, quantity_unit = ?, quantity_status = ?,
                       summary = ?, original_payload = ?, updated_at = ?
                       WHERE id = ?""",
                    (
                        record["canonical_name"],
                        record["incident_category"],
                        start_time,
                        end_time,
                        record["time_precision"],
                        record["country"],
                        record["location_description"],
                        record["latitude"],
                        record["longitude"],
                        "exact" if record["latitude"] is not None else None,
                        "source_record" if record["latitude"] is not None else None,
                        record["substance_name"],
                        record["substance_category"],
                        record["quantity_max"],
                        record["quantity_unit"],
                        record["quantity_status"],
                        record["summary"],
                        json.dumps(record["original_payload"]),
                        now,
                        incident_id,
                    ),
                )
                outcome = "updated"
            else:
                values = (
                    incident_id,
                    NOAA_SOURCE_ID,
                    record["source_record_id"],
                    record["canonical_name"],
                    record["incident_category"],
                    "source_imported",
                    start_time,
                    end_time,
                    record["time_precision"],
                    record["country"],
                    record["location_description"],
                    record["latitude"],
                    record["longitude"],
                    "exact" if record["latitude"] is not None else None,
                    "source_record" if record["latitude"] is not None else None,
                    record["substance_name"],
                    record["substance_category"],
                    record["quantity_max"],
                    record["quantity_unit"],
                    record["quantity_status"],
                    record["summary"],
                    json.dumps(record["original_payload"]),
                    now,
                    now,
                )
                placeholders = ", ".join(["?"] * len(values))
                sql = (
                    "INSERT INTO historical_incidents ("
                    "id, source_id, source_record_id, canonical_name, "
                    "incident_category, verification_status, start_time_utc, "
                    "end_time_utc, time_precision, country, location_description, "
                    "latitude, longitude, coordinate_accuracy, location_method, "
                    "substance_name, substance_category, quantity_max, "
                    "quantity_unit, quantity_status, summary, original_payload, "
                    "created_at, updated_at) VALUES (" + placeholders + ")"
                )
                conn.execute(sql, values)
                outcome = "created"

            # Source row (upsert on URL, the natural document key).
            source_url = _noaa_source_url(record["source_record_id"])
            src = conn.execute(
                "SELECT id FROM historical_incident_sources WHERE incident_id = ? AND source_url = ?",
                (incident_id, source_url),
            ).fetchone()
            if src:
                source_row_id = src["id"]
                conn.execute(
                    """UPDATE historical_incident_sources SET accessed_at = ?,
                       source_quality = 'official_documentation' WHERE id = ?""",
                    (now, source_row_id),
                )
            else:
                conn.execute(
                    """INSERT INTO historical_incident_sources (
                       id, incident_id, organization, source_title, source_url,
                       publication_date, accessed_at, source_type,
                       licence_or_usage_note, source_quality, created_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        source_row_id,
                        incident_id,
                        NOAA_ORGANIZATION,
                        f"{NOAA_DATASET} — {record['canonical_name']}",
                        source_url,
                        record["start_time_utc"],
                        now,
                        "public_dataset",
                        NOAA_LIMITATION,
                        "official_documentation",
                        now,
                    ),
                )

        # Field-level provenance is refreshed in a second transaction so the
        # parent incident/source rows are committed first. (Python 3.14's
        # bundled sqlite3 driver surfaced an inconsistent immediate-FK error
        # when the child insert ran inside the same uncommitted transaction;
        # splitting the transactions keeps the refresh portable and correct.)
        self._refresh_field_provenance(incident_id, source_row_id, record, source_url)
        return outcome

    @staticmethod
    def _refresh_field_provenance(
        incident_id: str,
        source_row_id: str,
        record: dict[str, Any],
        source_url: str,
    ) -> None:
        """Replace field-level provenance rows for (incident, source)."""
        start_time = record["start_time_utc"]
        field_rows = [
            (incident_id, source_row_id, field, str(value), method, confidence)
            for field, value, method, confidence in [
                ("canonical_name", record["canonical_name"], "copied", "high"),
                ("start_time_utc", start_time, "parsed date from source", "high"),
                (
                    "location_description",
                    record["location_description"],
                    "copied",
                    "high",
                ),
                ("latitude", record["latitude"], "copied numeric", "high"),
                ("longitude", record["longitude"], "copied numeric", "high"),
                (
                    "country",
                    record["country"],
                    "parsed from source location text",
                    "medium" if record["country"] else "low",
                ),
                ("incident_category", record["incident_category"], "copied", "high"),
                ("substance_name", record["substance_name"], "copied", "high"),
                ("quantity_max", record["quantity_max"], "parsed numeric", "high"),
                ("summary", record["summary"], "copied", "high"),
                ("source_url", source_url, "derived", "high"),
            ]
            if value is not None
        ]
        # Field rows are upserted on the (incident, source, field) unique key
        # so re-imports stay idempotent. field_row order is
        # (incident_id, source_id, field_name, value, method, confidence).
        with get_db() as conn:
            for field_row in field_rows:
                conn.execute(
                    """INSERT OR IGNORE INTO historical_incident_field_sources
                       (incident_id, source_id, field_name, source_value,
                        normalization_method, confidence_level)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    field_row,
                )
                conn.execute(
                    """UPDATE historical_incident_field_sources SET
                       source_value = ?, normalization_method = ?,
                       confidence_level = ?
                       WHERE incident_id = ? AND source_id = ? AND field_name = ?""",
                    (
                        field_row[3],
                        field_row[4],
                        field_row[5],
                        field_row[0],
                        field_row[1],
                        field_row[2],
                    ),
                )

    # ── Queries ────────────────────────────────────────────────────────

    def list_incidents(
        self,
        *,
        search: str | None = None,
        country: str | None = None,
        category: str | None = None,
        source: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        verification_status: str | None = None,
        satellite_status: str | None = None,
        coordinate_accuracy: str | None = None,
        sort: str = "date_desc",
        limit: int = 25,
        offset: int = 0,
        cursor: str | None = None,
    ) -> dict[str, Any]:
        """List incidents with server-side filtering and stable pagination.

        Supports both offset pagination and keyset ``cursor`` pagination on the
        default date_desc ordering ((start_time_utc, id) descending). Cursor
        values are opaque strings: ``<iso-start>|<incident-id>``.
        """
        limit = max(1, min(limit, 100))
        offset = max(0, offset)

        where: list[str] = []
        params: list[Any] = []

        if search:
            like = f"%{search}%"
            where.append(
                "(canonical_name LIKE ? OR alternative_names LIKE ? OR "
                "location_description LIKE ? OR summary LIKE ? OR "
                "substance_name LIKE ? OR country LIKE ?)"
            )
            params.extend([like, like, like, like, like, like])
        if country:
            where.append("country = ?")
            params.append(country)
        if category:
            where.append("incident_category = ?")
            params.append(category)
        if source:
            where.append("source_id = ?")
            params.append(source)
        if verification_status:
            where.append("verification_status = ?")
            params.append(verification_status)
        if coordinate_accuracy:
            where.append("coordinate_accuracy = ?")
            params.append(coordinate_accuracy)
        if start_date:
            where.append("start_time_utc >= ?")
            params.append(f"{start_date}T00:00:00Z")
        if end_date:
            where.append("start_time_utc < ?")
            end = datetime.fromisoformat(f"{end_date}T00:00:00Z") + timedelta(days=1)
            params.append(end.strftime("%Y-%m-%dT%H:%M:%SZ"))

        if satellite_status == "matched":
            where.append(
                "EXISTS (SELECT 1 FROM satellite_catalog_matches m "
                "WHERE m.historical_incident_id = historical_incidents.id)"
            )
        elif satellite_status == "unmatched":
            where.append(
                "NOT EXISTS (SELECT 1 FROM satellite_catalog_matches m "
                "WHERE m.historical_incident_id = historical_incidents.id)"
            )

        where_sql = " WHERE " + " AND ".join(where) if where else ""

        order_map = {
            "date_desc": "historical_incidents.start_time_utc DESC, historical_incidents.id ASC",
            "date_asc": "historical_incidents.start_time_utc ASC, historical_incidents.id ASC",
            "name_asc": "historical_incidents.canonical_name COLLATE NOCASE ASC, historical_incidents.id ASC",
        }
        order_sql = order_map.get(sort, order_map["date_desc"])

        # Keyset cursor only applies to the default date_desc ordering. It is
        # appended as a full predicate (never bare "AND") and never leaks into
        # the plain filter params used by the COUNT query.
        cursor_predicate = ""
        cursor_params: list[Any] = []
        if cursor and sort == "date_desc" and cursor.count("|") == 1:
            cursor_time, cursor_id = cursor.split("|", 1)
            cursor_predicate = (
                "(historical_incidents.start_time_utc < ? OR "
                "(historical_incidents.start_time_utc = ? AND historical_incidents.id > ?))"
            )
            cursor_params = [cursor_time, cursor_time, cursor_id]

        with get_db() as conn:
            total = conn.execute(
                f"SELECT COUNT(*) FROM historical_incidents{where_sql}", params
            ).fetchone()[0]

            if cursor_predicate:
                fetch_where = " WHERE " + " AND ".join(where + [cursor_predicate])
                rows = conn.execute(
                    f"SELECT * FROM historical_incidents{fetch_where} ORDER BY {order_sql} LIMIT ?",
                    params + cursor_params + [limit],
                ).fetchall()
            else:
                rows = conn.execute(
                    f"SELECT * FROM historical_incidents{where_sql} "
                    f"ORDER BY {order_sql} LIMIT ? OFFSET ?",
                    params + [limit, offset],
                ).fetchall()

            items = [self._to_summary(row, conn) for row in rows]
            next_cursor = None
            if items and sort == "date_desc" and len(rows) == limit and not cursor_predicate:
                last = rows[-1]
                next_cursor = f"{last['start_time_utc']}|{last['id']}"

        return {
            "total": total,
            "items": items,
            "limit": limit,
            "offset": offset,
            "next_cursor": next_cursor,
        }

    def _to_summary(self, row: Any, conn: Any) -> dict[str, Any]:
        """Map-summary fields only — never full source documents."""
        sat_count = conn.execute(
            "SELECT COUNT(*) FROM satellite_catalog_matches WHERE historical_incident_id = ?",
            (row["id"],),
        ).fetchone()[0]
        return {
            "id": row["id"],
            "canonical_name": row["canonical_name"],
            "incident_category": row["incident_category"],
            "verification_status": row["verification_status"],
            "start_time_utc": row["start_time_utc"],
            "time_precision": row["time_precision"],
            "country": row["country"],
            "location_description": row["location_description"],
            "latitude": row["latitude"],
            "longitude": row["longitude"],
            "coordinate_accuracy": row["coordinate_accuracy"],
            "location_method": row["location_method"],
            "source_id": row["source_id"],
            "substance_name": row["substance_name"],
            "satellite_status": "matched" if sat_count > 0 else "unmatched",
            "satellite_match_count": sat_count,
        }

    def get_incident(self, incident_id: str) -> dict[str, Any] | None:
        """Full normalized detail with all provenance sections."""
        with get_db() as conn:
            row = conn.execute(
                "SELECT * FROM historical_incidents WHERE id = ?", (incident_id,)
            ).fetchone()
            if row is None:
                return None

            sources = [
                dict(s)
                for s in conn.execute(
                    "SELECT * FROM historical_incident_sources WHERE incident_id = ? ORDER BY created_at",
                    (incident_id,),
                ).fetchall()
            ]
            field_rows = conn.execute(
                """SELECT f.field_name, f.source_value, f.normalization_method,
                          f.confidence_level, f.curator_note, s.organization,
                          s.source_url, s.source_title
                   FROM historical_incident_field_sources f
                   JOIN historical_incident_sources s ON s.id = f.source_id
                   WHERE f.incident_id = ? ORDER BY f.field_name""",
                (incident_id,),
            ).fetchall()
            field_provenance: dict[str, list[dict[str, Any]]] = {}
            for fr in field_rows:
                field_provenance.setdefault(fr["field_name"], []).append(dict(fr))
            vessels = [
                dict(v)
                for v in conn.execute(
                    "SELECT * FROM historical_incident_vessels WHERE incident_id = ?",
                    (incident_id,),
                ).fetchall()
            ]
            impacts = [
                dict(v)
                for v in conn.execute(
                    "SELECT * FROM historical_incident_impacts WHERE incident_id = ?",
                    (incident_id,),
                ).fetchall()
            ]
            responses = [
                dict(v)
                for v in conn.execute(
                    "SELECT * FROM historical_incident_responses WHERE incident_id = ?",
                    (incident_id,),
                ).fetchall()
            ]
            matches = [
                dict(m)
                for m in conn.execute(
                    "SELECT * FROM satellite_catalog_matches WHERE historical_incident_id = ? "
                    "ORDER BY acquisition_start DESC",
                    (incident_id,),
                ).fetchall()
            ]
            linked_cases = [
                dict(c)
                for c in conn.execute(
                    "SELECT id, title, created_at FROM cases WHERE historical_incident_id = ? ORDER BY created_at DESC",
                    (incident_id,),
                ).fetchall()
            ]

        detail = dict(row)
        for json_col in ("alternative_names", "original_payload"):
            try:
                detail[json_col] = json.loads(
                    detail.get(json_col) or "[]"
                    if json_col == "alternative_names"
                    else detail.get(json_col) or "{}"
                )
            except (ValueError, TypeError):
                detail[json_col] = None

        sat_summary = self._satellite_summary(detail, matches)
        return {
            **detail,
            "sources": sources,
            "field_provenance": field_provenance,
            "vessels": vessels,
            "impacts": impacts,
            "responses": responses,
            "satellite_matches": matches,
            "satellite_summary": sat_summary,
            "linked_cases": linked_cases,
        }

    def _satellite_summary(
        self, incident: dict[str, Any], matches: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """Honest satellite availability summary for an incident."""
        if incident.get("latitude") is None or incident.get("longitude") is None:
            return {
                "available": False,
                "reason": "No source-reported coordinates — satellite search requires a location.",
                "match_count": 0,
                "nearest": None,
            }
        if not matches:
            return {
                "available": True,
                "reason": "No catalogue search has been run for this incident yet.",
                "match_count": 0,
                "nearest": None,
            }
        incident_time = incident.get("start_time_utc")
        nearest = None
        if incident_time:
            try:
                incident_dt = datetime.fromisoformat(incident_time)

                def dist(m: dict[str, Any]) -> float:
                    if not m.get("acquisition_start"):
                        return float("inf")
                    try:
                        return abs(
                            (
                                datetime.fromisoformat(m["acquisition_start"]) - incident_dt
                            ).total_seconds()
                        )
                    except ValueError:
                        return float("inf")

                best = min(matches, key=dist)
                if best.get("acquisition_start"):
                    nearest = {
                        "item_id": best["item_id"],
                        "product_identifier": best["product_identifier"],
                        "acquisition_start": best["acquisition_start"],
                        "temporal_distance_hours": best["temporal_distance_hours"],
                    }
            except ValueError:
                nearest = None
        return {
            "available": True,
            "reason": (
                "Catalogue matches confirm the area was observed by Sentinel-1. "
                "They do not prove oil is visible in any image."
            ),
            "match_count": len(matches),
            "nearest": nearest,
        }

    # ── Map GeoJSON ────────────────────────────────────────────────────

    def map_features(
        self,
        west: float,
        south: float,
        east: float,
        north: float,
        *,
        search: str | None = None,
        country: str | None = None,
        category: str | None = None,
        source: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        satellite_status: str | None = None,
    ) -> dict[str, Any]:
        """Bounded GeoJSON FeatureCollection of incidents with coordinates.

        Optional filters mirror the list endpoint so the map and sidebar stay
        consistent; only incidents with usable coordinates are mapped.
        """
        where: list[str] = [
            "latitude IS NOT NULL AND longitude IS NOT NULL",
            "latitude BETWEEN ? AND ?",
            "longitude BETWEEN ? AND ?",
        ]
        params: list[Any] = [south, north, west, east]
        if search:
            like = f"%{search}%"
            where.append(
                "(canonical_name LIKE ? OR location_description LIKE ? OR "
                "substance_name LIKE ? OR summary LIKE ? OR country LIKE ?)"
            )
            params.extend([like, like, like, like, like])
        if country:
            where.append("country = ?")
            params.append(country)
        if category:
            where.append("incident_category = ?")
            params.append(category)
        if source:
            where.append("source_id = ?")
            params.append(source)
        if start_date:
            where.append("start_time_utc >= ?")
            params.append(f"{start_date}T00:00:00Z")
        if end_date:
            end = datetime.fromisoformat(f"{end_date}T00:00:00Z") + timedelta(days=1)
            where.append("start_time_utc < ?")
            params.append(end.strftime("%Y-%m-%dT%H:%M:%SZ"))
        if satellite_status == "matched":
            where.append(
                "EXISTS (SELECT 1 FROM satellite_catalog_matches m "
                "WHERE m.historical_incident_id = historical_incidents.id)"
            )
        elif satellite_status == "unmatched":
            where.append(
                "NOT EXISTS (SELECT 1 FROM satellite_catalog_matches m "
                "WHERE m.historical_incident_id = historical_incidents.id)"
            )

        with get_db() as conn:
            rows = conn.execute(
                """SELECT id, canonical_name, incident_category, start_time_utc,
                          country, latitude, longitude, coordinate_accuracy,
                          location_method, source_id, verification_status,
                          (SELECT COUNT(*) FROM satellite_catalog_matches m
                           WHERE m.historical_incident_id = historical_incidents.id) AS sat_count
                   FROM historical_incidents
                   WHERE """
                + " AND ".join(where)
                + " ORDER BY start_time_utc DESC",
                params,
            ).fetchall()
        features = []
        for row in rows:
            features.append(
                {
                    "type": "Feature",
                    "id": row["id"],
                    "geometry": {
                        "type": "Point",
                        "coordinates": [row["longitude"], row["latitude"]],
                    },
                    "properties": {
                        "incident_id": row["id"],
                        "name": row["canonical_name"],
                        "category": row["incident_category"],
                        "date": row["start_time_utc"],
                        "country": row["country"],
                        "coordinate_accuracy": row["coordinate_accuracy"],
                        "location_method": row["location_method"],
                        "source_id": row["source_id"],
                        "verification_status": row["verification_status"],
                        "satellite_status": "matched" if row["sat_count"] > 0 else "unmatched",
                    },
                }
            )
        return {"type": "FeatureCollection", "features": features}

    # ── Satellite matches ──────────────────────────────────────────────

    def store_satellite_matches(self, incident_id: str, matches: list[dict[str, Any]]) -> int:
        """Persist metadata-only STAC matches (idempotent per item)."""
        now = _now_iso()
        count = 0
        with get_db() as conn:
            exists = conn.execute(
                "SELECT id FROM historical_incidents WHERE id = ?", (incident_id,)
            ).fetchone()
            if exists is None:
                raise HTTPException(status_code=404, detail=f"Incident not found: {incident_id}")
            for match in matches:
                conn.execute(
                    """INSERT INTO satellite_catalog_matches (
                       id, historical_incident_id, provider, collection, item_id,
                       product_identifier, platform, acquisition_start,
                       acquisition_end, acquisition_mode, processing_level,
                       polarizations, orbit_direction, geometry_geojson, bbox,
                       metadata_url, asset_access_status, temporal_distance_hours,
                       spatial_overlap_ratio, catalogue_checked_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                       ON CONFLICT(historical_incident_id, item_id) DO UPDATE SET
                       acquisition_start = excluded.acquisition_start,
                       acquisition_end = excluded.acquisition_end,
                       catalogue_checked_at = excluded.catalogue_checked_at""",
                    (
                        _new_id("sat"),
                        incident_id,
                        match.get("provider", "Copernicus Data Space Ecosystem"),
                        match.get("collection", "sentinel-1-grd"),
                        match["item_id"],
                        match.get("product_identifier"),
                        match.get("platform"),
                        match.get("acquisition_start"),
                        match.get("acquisition_end"),
                        match.get("acquisition_mode"),
                        match.get("processing_level"),
                        json.dumps(match.get("polarizations") or []),
                        match.get("orbit_direction"),
                        json.dumps(match.get("geometry_geojson")),
                        json.dumps(match.get("bbox")),
                        match.get("metadata_url"),
                        "metadata_only",
                        match.get("temporal_distance_hours"),
                        match.get("spatial_overlap_ratio"),
                        now,
                    ),
                )
                count += 1
        return count

    # ── Filters for the UI ─────────────────────────────────────────────

    def list_import_runs(self, limit: int = 10) -> list[dict[str, Any]]:
        """Recent import-run metadata for auditability."""
        with get_db() as conn:
            rows = conn.execute(
                "SELECT * FROM historical_incident_import_runs ORDER BY id DESC LIMIT ?",
                (max(1, min(limit, 50)),),
            ).fetchall()
        runs = []
        for row in rows:
            run = dict(row)
            try:
                run["rejection_report"] = json.loads(run.get("rejection_report") or "[]")
            except (ValueError, TypeError):
                run["rejection_report"] = []
            runs.append(run)
        return runs

    def filter_options(self) -> dict[str, Any]:
        """Distinct option lists for the explorer filters (real data only)."""
        with get_db() as conn:
            categories = [
                r[0]
                for r in conn.execute(
                    "SELECT DISTINCT incident_category FROM historical_incidents "
                    "WHERE incident_category IS NOT NULL ORDER BY incident_category"
                ).fetchall()
            ]
            countries = [
                r[0]
                for r in conn.execute(
                    "SELECT DISTINCT country FROM historical_incidents "
                    "WHERE country IS NOT NULL ORDER BY country"
                ).fetchall()
            ]
            sources = [
                {"id": r[0], "name": r[1]}
                for r in conn.execute(
                    "SELECT DISTINCT h.source_id, s.organization FROM historical_incidents h "
                    "JOIN historical_incident_sources s ON s.incident_id = h.id "
                    "ORDER BY s.organization"
                ).fetchall()
            ]
            year_range = conn.execute(
                "SELECT MIN(start_time_utc), MAX(start_time_utc) FROM historical_incidents"
            ).fetchone()
        return {
            "categories": categories,
            "countries": countries,
            "sources": sources,
            "year_min": year_range[0][:4] if year_range and year_range[0] else None,
            "year_max": year_range[1][:4] if year_range and year_range[1] else None,
        }


historical_service = HistoricalIncidentService()
