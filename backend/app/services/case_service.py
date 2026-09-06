"""
Oilora Blue AI — Case Management Service

Handles case CRUD operations with SQLite persistence.
"""

import json
import uuid
from datetime import UTC, datetime
from typing import Any

from ..database import get_db


class CaseService:
    """Service for case CRUD operations."""

    @staticmethod
    def generate_id() -> str:
        return f"case-{uuid.uuid4().hex[:12]}"

    @staticmethod
    def now_iso() -> str:
        return datetime.now(UTC).isoformat()

    @classmethod
    def create_case(cls, data: dict[str, Any]) -> dict[str, Any]:
        """Create a new investigation case."""
        case_id = cls.generate_id()
        now = cls.now_iso()

        with get_db() as conn:
            conn.execute(
                """INSERT INTO cases (
                    id, title, description, region, incident_time, observation_time,
                    bbox_min_lat, bbox_min_lon, bbox_max_lat, bbox_max_lon,
                    analyst_notes, status, current_stage, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    case_id,
                    data["title"],
                    data.get("description", ""),
                    data.get("region", ""),
                    data.get("incident_time"),
                    data.get("observation_time"),
                    data.get("bbox_min_lat"),
                    data.get("bbox_min_lon"),
                    data.get("bbox_max_lat"),
                    data.get("bbox_max_lon"),
                    data.get("analyst_notes", ""),
                    "created",
                    "registration",
                    now,
                    now,
                ),
            )

            # Log audit event
            conn.execute(
                """INSERT INTO audit_log (case_id, event_type, event_data, created_at)
                   VALUES (?, ?, ?, ?)""",
                (case_id, "case_created", json.dumps({"title": data["title"]}), now),
            )

        return cls.get_case(case_id)  # type: ignore

    @classmethod
    def get_case(cls, case_id: str) -> dict[str, Any] | None:
        """Get a single case by ID."""
        with get_db() as conn:
            row = conn.execute("SELECT * FROM cases WHERE id = ?", (case_id,)).fetchone()
            if row is None:
                return None
            return cls._row_to_dict(row)

    @classmethod
    def list_cases(cls, offset: int = 0, limit: int = 50) -> tuple[list[dict[str, Any]], int]:
        """List all cases with pagination."""
        with get_db() as conn:
            total = conn.execute("SELECT COUNT(*) FROM cases").fetchone()[0]
            rows = conn.execute(
                "SELECT * FROM cases ORDER BY updated_at DESC LIMIT ? OFFSET ?",
                (limit, offset),
            ).fetchall()
            cases = [cls._row_to_dict(row) for row in rows]

            # Add file counts
            for case in cases:
                count = conn.execute(
                    "SELECT COUNT(*) FROM files WHERE case_id = ?", (case["id"],)
                ).fetchone()[0]
                case["file_count"] = count

            return cases, total

    @classmethod
    def update_case(cls, case_id: str, data: dict[str, Any]) -> dict[str, Any] | None:
        """Update a case."""
        updates = {k: v for k, v in data.items() if v is not None}
        if not updates:
            return cls.get_case(case_id)

        updates["updated_at"] = cls.now_iso()
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        values = list(updates.values()) + [case_id]

        with get_db() as conn:
            result = conn.execute(f"UPDATE cases SET {set_clause} WHERE id = ?", values)
            if result.rowcount == 0:
                return None

            conn.execute(
                """INSERT INTO audit_log (case_id, event_type, event_data, created_at)
                   VALUES (?, ?, ?, ?)""",
                (case_id, "case_updated", json.dumps(updates), cls.now_iso()),
            )

        return cls.get_case(case_id)

    @classmethod
    def delete_case(cls, case_id: str) -> bool:
        """Delete a case and all associated data."""
        with get_db() as conn:
            result = conn.execute("DELETE FROM cases WHERE id = ?", (case_id,))
            return result.rowcount > 0

    @classmethod
    def update_stage(cls, case_id: str, stage: str, status: str | None = None) -> None:
        """Update the current processing stage of a case."""
        now = cls.now_iso()
        with get_db() as conn:
            if status:
                conn.execute(
                    "UPDATE cases SET current_stage = ?, status = ?, updated_at = ? WHERE id = ?",
                    (stage, status, now, case_id),
                )
            else:
                conn.execute(
                    "UPDATE cases SET current_stage = ?, updated_at = ? WHERE id = ?",
                    (stage, now, case_id),
                )

            conn.execute(
                """INSERT INTO audit_log (case_id, event_type, event_data, created_at)
                   VALUES (?, ?, ?, ?)""",
                (case_id, "stage_changed", json.dumps({"stage": stage, "status": status}), now),
            )

    @staticmethod
    def _row_to_dict(row: Any) -> dict[str, Any]:
        """Convert a SQLite Row to a dictionary."""
        d = dict(row)
        # Convert boolean fields
        for key in ["dataset_ready", "system_ready", "offline_ready"]:
            if key in d:
                d[key] = bool(d[key])
        return d


case_service = CaseService()
