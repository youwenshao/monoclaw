"""SMS fallback handler for patients without WhatsApp."""

from __future__ import annotations

import logging
from pathlib import Path

from openclaw_shared.database import get_db

logger = logging.getLogger("openclaw.medical-dental.med_reminder.sms")

_TAKEN_KEYWORDS = {"taken", "ok", "yes", "done", "已服", "已食", "食咗"}


class SmsFallbackHandler:
    """Build concise SMS reminders and parse short-form replies."""

    def send_reminder(
        self,
        phone: str,
        medication_name: str,
        dosage: str,
        language: str,
    ) -> bool:
        """Build and return an SMS reminder body.

        Returns True if the message was built successfully.
        Actual sending is delegated to the messaging provider at the caller level.
        """
        text = self._build_reminder_text(medication_name, dosage, language)
        if not text:
            return False

        logger.info("SMS reminder prepared for %s: %s", phone, text[:60])
        return True

    def get_reminder_text(
        self,
        medication_name: str,
        dosage: str,
        language: str,
    ) -> str:
        """Return the SMS body without sending it."""
        return self._build_reminder_text(medication_name, dosage, language)

    def parse_response(
        self,
        from_phone: str,
        text: str,
    ) -> dict:
        """Parse an inbound SMS reply.

        Returns dict with keys:
        - type: "taken" | "unknown"
        - medication_id: int | None
        """
        normalised = text.strip().lower()
        if normalised in _TAKEN_KEYWORDS:
            return {"type": "taken", "medication_id": None}
        return {"type": "unknown", "medication_id": None}

    @staticmethod
    def _build_reminder_text(medication_name: str, dosage: str, language: str) -> str:
        if language in ("tc", "zh"):
            return f"食藥提醒：{medication_name} {dosage}。已服請回覆「已服」。"
        return f"Med reminder: {medication_name} {dosage}. Reply 'taken' to confirm."
