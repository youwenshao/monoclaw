"""Consultation note finalization and amendment logic."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from openclaw_shared.database import get_db

logger = logging.getLogger("openclaw.scribe-ai.finalization")


class Finalization:
    """Handles note finalization (immutability) and amendment workflow."""

    def finalize_note(
        self,
        db_path: str | Path,
        consultation_id: int,
        finalized_by: str,
    ) -> bool:
        """Finalize a consultation note, making it immutable.

        Returns True on success, False if already finalized or not found.
        """
        with get_db(db_path) as conn:
            row = conn.execute(
                "SELECT id, status FROM consultations WHERE id = ?",
                (consultation_id,),
            ).fetchone()

            if row is None:
                logger.warning("Consultation #%d not found", consultation_id)
                return False

            if row["status"] == "finalized":
                logger.info("Consultation #%d already finalized", consultation_id)
                return False

            now = datetime.now().isoformat()
            conn.execute(
                """UPDATE consultations
                   SET status = 'finalized', finalized_at = ?, finalized_by = ?
                   WHERE id = ?""",
                (now, finalized_by, consultation_id),
            )

        logger.info(
            "Consultation #%d finalized by %s", consultation_id, finalized_by
        )
        return True

    def amend_note(
        self,
        db_path: str | Path,
        consultation_id: int,
        amended_by: str,
        soap_data: dict[str, str],
        *,
        icd10_codes: list[str] | None = None,
        medications: list[str] | None = None,
        follow_up_date: str | None = None,
    ) -> int:
        """Create an amendment to a finalized note.

        The original note remains immutable. A new consultation record is
        created with amendment_of pointing to the original.
        Returns the new consultation ID.
        """
        with get_db(db_path) as conn:
            original = conn.execute(
                "SELECT * FROM consultations WHERE id = ?",
                (consultation_id,),
            ).fetchone()

            if original is None:
                raise ValueError(f"Consultation #{consultation_id} not found")

            orig = dict(original)

            cursor = conn.execute(
                """INSERT INTO consultations
                   (patient_id, doctor, raw_transcription, audio_path,
                    soap_subjective, soap_objective, soap_assessment, soap_plan,
                    icd10_codes, medications_prescribed, follow_up_date,
                    status, amendment_of)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    orig["patient_id"],
                    amended_by,
                    orig.get("raw_transcription", ""),
                    orig.get("audio_path", ""),
                    soap_data.get("subjective", orig.get("soap_subjective", "")),
                    soap_data.get("objective", orig.get("soap_objective", "")),
                    soap_data.get("assessment", orig.get("soap_assessment", "")),
                    soap_data.get("plan", orig.get("soap_plan", "")),
                    json.dumps(icd10_codes) if icd10_codes is not None else orig.get("icd10_codes", "[]"),
                    json.dumps(medications) if medications is not None else orig.get("medications_prescribed", "[]"),
                    follow_up_date or orig.get("follow_up_date"),
                    "draft",
                    consultation_id,
                ),
            )
            new_id = cursor.lastrowid

        logger.info(
            "Amendment #%d created for consultation #%d by %s",
            new_id,
            consultation_id,
            amended_by,
        )
        return new_id  # type: ignore[return-value]
