"""Refill request lifecycle management."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from openclaw_shared.database import get_db

logger = logging.getLogger("openclaw.medical-dental.med_reminder.refill")

VALID_TRANSITIONS: dict[str, set[str]] = {
    "pending": {"approved", "modified", "rejected"},
    "approved": {"ready"},
    "modified": {"ready"},
    "rejected": set(),
    "ready": {"collected"},
    "collected": set(),
}


class RefillWorkflow:
    """Manage refill request state machine: pending -> approved/modified/rejected -> ready -> collected."""

    def create_request(
        self,
        db_path: str | Path,
        patient_id: int,
        medication_id: int,
        photo_path: str | None = None,
        ocr_result: str | None = None,
    ) -> int:
        """Create a new refill request. Returns the request ID."""
        with get_db(db_path) as conn:
            cursor = conn.execute(
                """INSERT INTO refill_requests
                   (patient_id, medication_id, photo_path, ocr_result, status)
                   VALUES (?, ?, ?, ?, 'pending')""",
                (patient_id, medication_id, photo_path, ocr_result),
            )
            request_id: int = cursor.lastrowid  # type: ignore[assignment]

        logger.info(
            "Refill request #%d created: patient=%d med=%d",
            request_id, patient_id, medication_id,
        )
        return request_id

    def approve_request(
        self,
        db_path: str | Path,
        request_id: int,
        reviewed_by: str,
        notes: str | None = None,
    ) -> bool:
        """Approve a pending refill request. Checks Part I poison flag."""
        return self._transition(db_path, request_id, "approved", reviewed_by, notes)

    def reject_request(
        self,
        db_path: str | Path,
        request_id: int,
        reviewed_by: str,
        reason: str,
    ) -> bool:
        """Reject a pending refill request."""
        return self._transition(db_path, request_id, "rejected", reviewed_by, reason)

    def mark_ready(
        self,
        db_path: str | Path,
        request_id: int,
    ) -> bool:
        """Mark an approved/modified request as ready for collection."""
        with get_db(db_path) as conn:
            row = conn.execute(
                "SELECT status FROM refill_requests WHERE id = ?", (request_id,)
            ).fetchone()
            if not row:
                return False

            current = row["status"]
            if "ready" not in VALID_TRANSITIONS.get(current, set()):
                logger.warning(
                    "Cannot mark request #%d ready — current status: %s", request_id, current
                )
                return False

            conn.execute(
                "UPDATE refill_requests SET status = 'ready', ready_at = ? WHERE id = ?",
                (datetime.now().isoformat(), request_id),
            )

        logger.info("Refill request #%d marked ready", request_id)
        return True

    def mark_collected(
        self,
        db_path: str | Path,
        request_id: int,
    ) -> bool:
        """Mark a ready request as collected by the patient."""
        with get_db(db_path) as conn:
            row = conn.execute(
                "SELECT status FROM refill_requests WHERE id = ?", (request_id,)
            ).fetchone()
            if not row:
                return False

            current = row["status"]
            if "collected" not in VALID_TRANSITIONS.get(current, set()):
                logger.warning(
                    "Cannot mark request #%d collected — current status: %s", request_id, current
                )
                return False

            conn.execute(
                "UPDATE refill_requests SET status = 'collected' WHERE id = ?",
                (request_id,),
            )

        logger.info("Refill request #%d collected", request_id)
        return True

    def get_pending_requests(
        self,
        db_path: str | Path,
    ) -> list[dict[str, Any]]:
        """Return all pending refill requests with patient and medication info."""
        with get_db(db_path) as conn:
            rows = conn.execute(
                """SELECT rr.*, p.name_en, p.name_tc, p.phone,
                          m.drug_name_en, m.drug_name_tc, m.dosage
                   FROM refill_requests rr
                   LEFT JOIN patients p ON p.id = rr.patient_id
                   LEFT JOIN medications m ON m.id = rr.medication_id
                   WHERE rr.status = 'pending'
                   ORDER BY rr.created_at ASC""",
            ).fetchall()
        return [dict(r) for r in rows]

    def get_patient_requests(
        self,
        db_path: str | Path,
        patient_id: int,
    ) -> list[dict[str, Any]]:
        """Return all refill requests for a patient."""
        with get_db(db_path) as conn:
            rows = conn.execute(
                """SELECT rr.*, m.drug_name_en, m.drug_name_tc, m.dosage
                   FROM refill_requests rr
                   LEFT JOIN medications m ON m.id = rr.medication_id
                   WHERE rr.patient_id = ?
                   ORDER BY rr.created_at DESC""",
                (patient_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------

    def _transition(
        self,
        db_path: str | Path,
        request_id: int,
        target_status: str,
        reviewed_by: str,
        notes: str | None,
    ) -> bool:
        with get_db(db_path) as conn:
            row = conn.execute(
                "SELECT * FROM refill_requests WHERE id = ?", (request_id,)
            ).fetchone()
            if not row:
                return False

            current = row["status"]
            if target_status not in VALID_TRANSITIONS.get(current, set()):
                logger.warning(
                    "Invalid transition %s -> %s for request #%d",
                    current, target_status, request_id,
                )
                return False

            conn.execute(
                """UPDATE refill_requests
                   SET status = ?, reviewed_by = ?, notes = ?
                   WHERE id = ?""",
                (target_status, reviewed_by, notes, request_id),
            )

        logger.info(
            "Refill request #%d: %s -> %s (by %s)",
            request_id, current, target_status, reviewed_by,
        )
        return True
