"""Consultation note CRUD operations against the scribe_ai database."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from openclaw_shared.database import get_db

logger = logging.getLogger("openclaw.scribe-ai.notes")


def _row_to_dict(row: Any) -> dict[str, Any]:
    """Convert a sqlite3.Row to a plain dict, deserializing JSON columns."""
    d = dict(row)
    for json_col in ("icd10_codes", "medications_prescribed"):
        if d.get(json_col) and isinstance(d[json_col], str):
            try:
                d[json_col] = json.loads(d[json_col])
            except (json.JSONDecodeError, TypeError):
                pass
    return d


class NoteManager:
    """CRUD operations for consultation notes in the scribe_ai database."""

    def create_note(
        self,
        db_path: str | Path,
        patient_id: int,
        doctor: str,
        soap_data: dict[str, str],
        *,
        raw_transcription: str = "",
        audio_path: str = "",
        icd10_codes: list[str] | None = None,
        medications: list[str] | None = None,
        follow_up_date: str | None = None,
        status: str = "draft",
    ) -> int:
        """Create a new consultation note. Returns the consultation ID."""
        with get_db(db_path) as conn:
            cursor = conn.execute(
                """INSERT INTO consultations
                   (patient_id, doctor, raw_transcription, audio_path,
                    soap_subjective, soap_objective, soap_assessment, soap_plan,
                    icd10_codes, medications_prescribed, follow_up_date, status)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    patient_id,
                    doctor,
                    raw_transcription,
                    audio_path,
                    soap_data.get("subjective", ""),
                    soap_data.get("objective", ""),
                    soap_data.get("assessment", ""),
                    soap_data.get("plan", ""),
                    json.dumps(icd10_codes or []),
                    json.dumps(medications or []),
                    follow_up_date,
                    status,
                ),
            )
            consultation_id = cursor.lastrowid

        logger.info(
            "Created consultation #%d for patient %d by %s",
            consultation_id,
            patient_id,
            doctor,
        )
        return consultation_id  # type: ignore[return-value]

    def get_note(self, db_path: str | Path, consultation_id: int) -> dict[str, Any] | None:
        """Retrieve a single consultation by ID."""
        with get_db(db_path) as conn:
            row = conn.execute(
                "SELECT * FROM consultations WHERE id = ?",
                (consultation_id,),
            ).fetchone()
        if row is None:
            return None
        return _row_to_dict(row)

    def get_patient_notes(
        self,
        db_path: str | Path,
        patient_id: int,
        *,
        status: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """List consultations for a patient, newest first."""
        params: list[Any] = [patient_id]
        where_clause = "WHERE patient_id = ?"
        if status:
            where_clause += " AND status = ?"
            params.append(status)
        params.append(limit)

        with get_db(db_path) as conn:
            rows = conn.execute(
                f"SELECT * FROM consultations {where_clause} "  # noqa: S608
                "ORDER BY consultation_date DESC LIMIT ?",
                params,
            ).fetchall()
        return [_row_to_dict(r) for r in rows]

    def update_note(
        self,
        db_path: str | Path,
        consultation_id: int,
        **fields: Any,
    ) -> bool:
        """Update mutable fields on a draft consultation. Returns True if updated."""
        with get_db(db_path) as conn:
            row = conn.execute(
                "SELECT status FROM consultations WHERE id = ?",
                (consultation_id,),
            ).fetchone()
            if row is None:
                return False
            if row["status"] == "finalized":
                logger.warning("Cannot update finalized consultation #%d", consultation_id)
                return False

            allowed = {
                "soap_subjective", "soap_objective", "soap_assessment", "soap_plan",
                "raw_transcription", "audio_path", "icd10_codes",
                "medications_prescribed", "follow_up_date", "status", "doctor",
            }
            updates: dict[str, Any] = {}
            for key, value in fields.items():
                if key in allowed:
                    if key in ("icd10_codes", "medications_prescribed") and isinstance(value, list):
                        updates[key] = json.dumps(value)
                    else:
                        updates[key] = value

            if not updates:
                return False

            set_clause = ", ".join(f"{k} = ?" for k in updates)
            params = list(updates.values()) + [consultation_id]
            conn.execute(
                f"UPDATE consultations SET {set_clause} WHERE id = ?",  # noqa: S608
                params,
            )

        logger.info("Updated consultation #%d: %s", consultation_id, list(updates.keys()))
        return True

    def list_consultations(
        self,
        db_path: str | Path,
        *,
        patient_id: int | None = None,
        status: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """List consultations with optional filters."""
        conditions: list[str] = []
        params: list[Any] = []

        if patient_id is not None:
            conditions.append("patient_id = ?")
            params.append(patient_id)
        if status:
            conditions.append("status = ?")
            params.append(status)

        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        params.append(limit)

        with get_db(db_path) as conn:
            rows = conn.execute(
                f"SELECT * FROM consultations {where} "  # noqa: S608
                "ORDER BY consultation_date DESC LIMIT ?",
                params,
            ).fetchall()
        return [_row_to_dict(r) for r in rows]
