"""Escalation logic for patients with low medication compliance."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from openclaw_shared.database import get_db

from medical_dental.med_reminder.reminders.compliance_tracker import ComplianceTracker

logger = logging.getLogger("openclaw.medical-dental.med_reminder.escalation")


class EscalationManager:
    """Identify and report patients requiring clinic follow-up due to poor adherence."""

    def __init__(self) -> None:
        self._tracker = ComplianceTracker()

    def check_escalations(
        self,
        db_path: str | Path,
        threshold_pct: float = 60,
    ) -> list[dict[str, Any]]:
        """Return patients whose compliance falls below *threshold_pct*.

        Each dict contains patient_id, name_en, name_tc, phone, compliance_rate.
        """
        return self._tracker.get_low_compliance_patients(db_path, threshold=threshold_pct)

    def generate_escalation_report(
        self,
        db_path: str | Path,
        patient_id: int,
    ) -> dict[str, Any]:
        """Produce a detailed escalation report for one patient.

        Returns:
            {
                "patient": { ... },
                "medications": [ ... ],
                "compliance": { per-medication rates },
                "trend": "improving" | "declining" | "stable",
                "generated_at": str,
            }
        """
        with get_db(db_path) as conn:
            patient_row = conn.execute(
                "SELECT * FROM patients WHERE id = ?", (patient_id,)
            ).fetchone()
            if not patient_row:
                return {"error": "Patient not found"}

            patient = dict(patient_row)

            medications = [
                dict(r) for r in conn.execute(
                    "SELECT * FROM medications WHERE patient_id = ? AND active = 1",
                    (patient_id,),
                ).fetchall()
            ]

        compliance = self._tracker.get_patient_compliance(db_path, patient_id, days=30)
        trend = self._compute_trend(db_path, patient_id)

        return {
            "patient": {
                "id": patient["id"],
                "name_en": patient.get("name_en"),
                "name_tc": patient.get("name_tc"),
                "phone": patient.get("phone"),
                "preferred_language": patient.get("preferred_language"),
            },
            "medications": [
                {
                    "id": m["id"],
                    "drug_name_en": m["drug_name_en"],
                    "drug_name_tc": m.get("drug_name_tc"),
                    "dosage": m.get("dosage"),
                    "frequency": m.get("frequency"),
                }
                for m in medications
            ],
            "compliance": compliance,
            "trend": trend,
            "generated_at": datetime.now().isoformat(),
        }

    # ------------------------------------------------------------------

    def _compute_trend(
        self,
        db_path: str | Path,
        patient_id: int,
    ) -> str:
        """Compare the recent 15-day compliance to the prior 15-day window."""
        now = datetime.now()
        mid = now - timedelta(days=15)
        start = now - timedelta(days=30)

        with get_db(db_path) as conn:
            recent = conn.execute(
                """SELECT
                       SUM(CASE WHEN taken = 1 THEN 1 ELSE 0 END) AS taken_count,
                       COUNT(*) AS total
                   FROM compliance_logs
                   WHERE patient_id = ? AND taken IS NOT NULL
                     AND (reminder_sent_at >= ? OR responded_at >= ?)""",
                (patient_id, mid.isoformat(), mid.isoformat()),
            ).fetchone()

            prior = conn.execute(
                """SELECT
                       SUM(CASE WHEN taken = 1 THEN 1 ELSE 0 END) AS taken_count,
                       COUNT(*) AS total
                   FROM compliance_logs
                   WHERE patient_id = ? AND taken IS NOT NULL
                     AND (reminder_sent_at >= ? OR responded_at >= ?)
                     AND (reminder_sent_at < ? OR responded_at < ?)""",
                (
                    patient_id,
                    start.isoformat(), start.isoformat(),
                    mid.isoformat(), mid.isoformat(),
                ),
            ).fetchone()

        recent_rate = _safe_rate(recent)
        prior_rate = _safe_rate(prior)

        if recent_rate > prior_rate + 5:
            return "improving"
        if recent_rate < prior_rate - 5:
            return "declining"
        return "stable"


def _safe_rate(row: Any) -> float:
    if not row or not row["total"]:
        return 0.0
    return (row["taken_count"] or 0) / row["total"] * 100
