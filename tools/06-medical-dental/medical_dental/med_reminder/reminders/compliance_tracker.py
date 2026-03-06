"""Track and report medication compliance rates."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from openclaw_shared.database import get_db

logger = logging.getLogger("openclaw.medical-dental.med_reminder.compliance")

COMPLIANCE_WINDOW_HOURS = 2


class ComplianceTracker:
    """Record and query medication adherence data."""

    def record_taken(
        self,
        db_path: str | Path,
        patient_id: int,
        medication_id: int,
    ) -> int:
        """Log a confirmed medication intake. Returns the log ID."""
        now = datetime.now().isoformat()
        with get_db(db_path) as conn:
            pending = conn.execute(
                """SELECT id FROM compliance_logs
                   WHERE patient_id = ? AND medication_id = ? AND taken IS NULL
                   ORDER BY reminder_sent_at DESC LIMIT 1""",
                (patient_id, medication_id),
            ).fetchone()

            if pending:
                conn.execute(
                    "UPDATE compliance_logs SET taken = 1, responded_at = ?, response = 'taken' WHERE id = ?",
                    (now, pending["id"]),
                )
                return pending["id"]

            cursor = conn.execute(
                """INSERT INTO compliance_logs
                   (patient_id, medication_id, responded_at, response, taken)
                   VALUES (?, ?, ?, 'taken', 1)""",
                (patient_id, medication_id, now),
            )
            return cursor.lastrowid  # type: ignore[return-value]

    def record_missed(
        self,
        db_path: str | Path,
        patient_id: int,
        medication_id: int,
        reminder_sent_at: str,
    ) -> int:
        """Mark a reminder as missed (no response within compliance window). Returns log ID."""
        with get_db(db_path) as conn:
            existing = conn.execute(
                """SELECT id, taken FROM compliance_logs
                   WHERE patient_id = ? AND medication_id = ? AND reminder_sent_at = ?""",
                (patient_id, medication_id, reminder_sent_at),
            ).fetchone()

            if existing:
                if existing["taken"] is None:
                    conn.execute(
                        "UPDATE compliance_logs SET taken = 0, response = 'missed' WHERE id = ?",
                        (existing["id"],),
                    )
                return existing["id"]

            cursor = conn.execute(
                """INSERT INTO compliance_logs
                   (patient_id, medication_id, reminder_sent_at, taken, response)
                   VALUES (?, ?, ?, 0, 'missed')""",
                (patient_id, medication_id, reminder_sent_at),
            )
            return cursor.lastrowid  # type: ignore[return-value]

    def get_patient_compliance(
        self,
        db_path: str | Path,
        patient_id: int,
        days: int = 30,
    ) -> dict[str, Any]:
        """Per-medication compliance rates for a patient over the last N days.

        Returns:
            {
                "patient_id": int,
                "period_days": int,
                "medications": [
                    {"medication_id": int, "drug_name_en": str, "taken": int, "missed": int, "rate": float},
                    ...
                ],
                "overall_rate": float,
            }
        """
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()

        with get_db(db_path) as conn:
            rows = conn.execute(
                """SELECT
                       cl.medication_id,
                       m.drug_name_en,
                       m.drug_name_tc,
                       SUM(CASE WHEN cl.taken = 1 THEN 1 ELSE 0 END) AS taken_count,
                       SUM(CASE WHEN cl.taken = 0 THEN 1 ELSE 0 END) AS missed_count,
                       COUNT(*) AS total
                   FROM compliance_logs cl
                   LEFT JOIN medications m ON m.id = cl.medication_id
                   WHERE cl.patient_id = ?
                     AND cl.taken IS NOT NULL
                     AND (cl.reminder_sent_at >= ? OR cl.responded_at >= ?)
                   GROUP BY cl.medication_id""",
                (patient_id, cutoff, cutoff),
            ).fetchall()

        medications: list[dict[str, Any]] = []
        total_taken = 0
        total_all = 0

        for r in rows:
            taken = r["taken_count"] or 0
            missed = r["missed_count"] or 0
            total = taken + missed
            rate = (taken / total * 100) if total > 0 else 0.0
            medications.append({
                "medication_id": r["medication_id"],
                "drug_name_en": r["drug_name_en"],
                "drug_name_tc": r["drug_name_tc"],
                "taken": taken,
                "missed": missed,
                "rate": round(rate, 1),
            })
            total_taken += taken
            total_all += total

        overall = (total_taken / total_all * 100) if total_all > 0 else 0.0

        return {
            "patient_id": patient_id,
            "period_days": days,
            "medications": medications,
            "overall_rate": round(overall, 1),
        }

    def get_medication_compliance(
        self,
        db_path: str | Path,
        medication_id: int,
        days: int = 30,
    ) -> float:
        """Single medication compliance percentage over N days."""
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()

        with get_db(db_path) as conn:
            row = conn.execute(
                """SELECT
                       SUM(CASE WHEN taken = 1 THEN 1 ELSE 0 END) AS taken_count,
                       COUNT(*) AS total
                   FROM compliance_logs
                   WHERE medication_id = ?
                     AND taken IS NOT NULL
                     AND (reminder_sent_at >= ? OR responded_at >= ?)""",
                (medication_id, cutoff, cutoff),
            ).fetchone()

        if not row or not row["total"]:
            return 0.0
        return round(row["taken_count"] / row["total"] * 100, 1)

    def get_low_compliance_patients(
        self,
        db_path: str | Path,
        threshold: float = 60,
    ) -> list[dict[str, Any]]:
        """Return patients whose overall compliance in the last 30 days is below threshold."""
        cutoff = (datetime.now() - timedelta(days=30)).isoformat()

        with get_db(db_path) as conn:
            rows = conn.execute(
                """SELECT
                       p.id AS patient_id,
                       p.name_en,
                       p.name_tc,
                       p.phone,
                       SUM(CASE WHEN cl.taken = 1 THEN 1 ELSE 0 END) AS taken_count,
                       COUNT(*) AS total
                   FROM compliance_logs cl
                   JOIN patients p ON p.id = cl.patient_id
                   WHERE cl.taken IS NOT NULL
                     AND (cl.reminder_sent_at >= ? OR cl.responded_at >= ?)
                   GROUP BY p.id
                   HAVING (CAST(SUM(CASE WHEN cl.taken = 1 THEN 1 ELSE 0 END) AS REAL) / COUNT(*)) * 100 < ?""",
                (cutoff, cutoff, threshold),
            ).fetchall()

        results: list[dict[str, Any]] = []
        for r in rows:
            taken = r["taken_count"] or 0
            total = r["total"] or 0
            rate = (taken / total * 100) if total > 0 else 0.0
            results.append({
                "patient_id": r["patient_id"],
                "name_en": r["name_en"],
                "name_tc": r["name_tc"],
                "phone": r["phone"],
                "compliance_rate": round(rate, 1),
                "taken": taken,
                "total": total,
            })

        return results
