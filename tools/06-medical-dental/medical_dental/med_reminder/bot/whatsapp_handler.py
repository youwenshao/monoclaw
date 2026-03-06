"""WhatsApp message handler for the MedReminder bot."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from openclaw_shared.database import get_db

from medical_dental.med_reminder.bot.message_templates import (
    photo_received,
    refill_request_received,
    taken_confirmation,
    unknown_message,
)

logger = logging.getLogger("openclaw.medical-dental.med_reminder.whatsapp")

_TAKEN_KEYWORDS = {"taken", "已服", "已食", "食咗", "ok", "done"}
_REFILL_KEYWORDS = {"refill", "補藥", "续药", "續藥"}


class MedReminderWhatsAppHandler:
    """Process incoming WhatsApp messages for medication reminders."""

    def __init__(self, db_path: str | Path, llm: Any | None = None) -> None:
        self._db_path = str(db_path)
        self._llm = llm

    def handle_message(
        self,
        from_phone: str,
        message_text: str,
        media_url: str | None = None,
    ) -> str:
        """Route an incoming message and return a response string."""
        patient = self._lookup_patient(from_phone)
        if patient is None:
            return (
                "This phone number is not registered. "
                "Please contact the clinic.\n"
                "此電話號碼尚未登記，請聯絡診所。"
            )

        language: str = patient.get("preferred_language", "en") or "en"

        if media_url:
            return self._handle_photo(patient, media_url, language)

        normalised = message_text.strip().lower()

        if normalised in _TAKEN_KEYWORDS:
            return self._handle_taken(patient, language)

        if normalised in _REFILL_KEYWORDS:
            return self._handle_refill_request(patient, language)

        return unknown_message(language)

    # ------------------------------------------------------------------
    # Internal handlers
    # ------------------------------------------------------------------

    def _handle_taken(self, patient: dict, language: str) -> str:
        """Mark the most recent pending reminder as taken."""
        now = datetime.now().isoformat()
        with get_db(self._db_path) as conn:
            pending = conn.execute(
                """SELECT cl.id, cl.medication_id
                   FROM compliance_logs cl
                   WHERE cl.patient_id = ?
                     AND cl.taken IS NULL
                   ORDER BY cl.reminder_sent_at DESC
                   LIMIT 1""",
                (patient["id"],),
            ).fetchone()

            if pending:
                conn.execute(
                    "UPDATE compliance_logs SET taken = 1, responded_at = ?, response = 'taken' WHERE id = ?",
                    (now, pending["id"]),
                )
            else:
                active_med = conn.execute(
                    "SELECT id FROM medications WHERE patient_id = ? AND active = 1 LIMIT 1",
                    (patient["id"],),
                ).fetchone()
                med_id = active_med["id"] if active_med else None
                conn.execute(
                    """INSERT INTO compliance_logs
                       (patient_id, medication_id, response, responded_at, taken)
                       VALUES (?, ?, 'taken', ?, 1)""",
                    (patient["id"], med_id, now),
                )

        return taken_confirmation(language)

    def _handle_refill_request(self, patient: dict, language: str) -> str:
        """Create a refill request for the patient's active medications."""
        with get_db(self._db_path) as conn:
            meds = conn.execute(
                "SELECT id FROM medications WHERE patient_id = ? AND active = 1 AND refill_eligible = 1",
                (patient["id"],),
            ).fetchall()
            for med in meds:
                existing = conn.execute(
                    """SELECT id FROM refill_requests
                       WHERE patient_id = ? AND medication_id = ? AND status = 'pending'""",
                    (patient["id"], med["id"]),
                ).fetchone()
                if not existing:
                    conn.execute(
                        """INSERT INTO refill_requests (patient_id, medication_id, status)
                           VALUES (?, ?, 'pending')""",
                        (patient["id"], med["id"]),
                    )

        return refill_request_received(language)

    def _handle_photo(self, patient: dict, media_url: str, language: str) -> str:
        """Create a refill request with a photo attachment for OCR processing."""
        with get_db(self._db_path) as conn:
            active_med = conn.execute(
                "SELECT id FROM medications WHERE patient_id = ? AND active = 1 AND refill_eligible = 1 LIMIT 1",
                (patient["id"],),
            ).fetchone()
            med_id = active_med["id"] if active_med else None
            conn.execute(
                """INSERT INTO refill_requests
                   (patient_id, medication_id, photo_path, status)
                   VALUES (?, ?, ?, 'pending')""",
                (patient["id"], med_id, media_url),
            )

        return photo_received(language)

    def _lookup_patient(self, phone: str) -> dict | None:
        """Find a patient by phone number (tries with and without whatsapp: prefix)."""
        clean_phone = phone.replace("whatsapp:", "").strip()
        with get_db(self._db_path) as conn:
            row = conn.execute(
                "SELECT * FROM patients WHERE phone = ?",
                (clean_phone,),
            ).fetchone()
            if row:
                return dict(row)
            if not clean_phone.startswith("+"):
                row = conn.execute(
                    "SELECT * FROM patients WHERE phone LIKE ?",
                    (f"%{clean_phone}",),
                ).fetchone()
                if row:
                    return dict(row)
        return None
