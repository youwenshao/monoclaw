"""Waitlist management for the ClinicScheduler."""

from __future__ import annotations

import logging
from datetime import date
from pathlib import Path
from typing import Any

from openclaw_shared.database import get_db

logger = logging.getLogger("openclaw.medical-dental.scheduler.waitlist")


class WaitlistManager:
    """Manages a priority-sorted waitlist for cancelled or unavailable slots."""

    def add_to_waitlist(self, db_path: str | Path, data: dict[str, Any]) -> int:
        required = ("patient_phone", "doctor_id", "preferred_date")
        for field in required:
            if field not in data:
                raise ValueError(f"Missing required field: {field}")

        with get_db(db_path) as conn:
            cursor = conn.execute(
                """INSERT INTO waitlist
                   (patient_phone, patient_name, doctor_id, preferred_date,
                    preferred_session, service_type, priority, status)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (
                    data["patient_phone"],
                    data.get("patient_name", ""),
                    data["doctor_id"],
                    data["preferred_date"],
                    data.get("preferred_session"),
                    data.get("service_type"),
                    data.get("priority", 0),
                    "waiting",
                ),
            )
            waitlist_id: int = cursor.lastrowid  # type: ignore[assignment]

        logger.info(
            "Added waitlist #%d for %s (doctor %s, date %s)",
            waitlist_id, data["patient_phone"], data["doctor_id"], data["preferred_date"],
        )
        return waitlist_id

    def get_waitlist(
        self,
        db_path: str | Path,
        doctor_id: int | None = None,
        target_date: date | None = None,
    ) -> list[dict[str, Any]]:
        conditions: list[str] = ["status = 'waiting'"]
        params: list[Any] = []

        if doctor_id is not None:
            conditions.append("doctor_id = ?")
            params.append(doctor_id)
        if target_date is not None:
            conditions.append("preferred_date = ?")
            params.append(target_date.isoformat())

        where = " AND ".join(conditions)

        with get_db(db_path) as conn:
            rows = conn.execute(
                f"SELECT * FROM waitlist WHERE {where} ORDER BY priority DESC, created_at ASC",  # noqa: S608
                params,
            ).fetchall()
        return [dict(r) for r in rows]

    def notify_available(self, db_path: str | Path, waitlist_id: int) -> bool:
        with get_db(db_path) as conn:
            row = conn.execute(
                "SELECT * FROM waitlist WHERE id = ? AND status = 'waiting'",
                (waitlist_id,),
            ).fetchone()
            if not row:
                return False

            conn.execute(
                """UPDATE waitlist
                   SET status = 'notified', notified_at = CURRENT_TIMESTAMP
                   WHERE id = ?""",
                (waitlist_id,),
            )

        logger.info("Notified waitlist #%d", waitlist_id)
        return True

    def match_cancellation(
        self,
        db_path: str | Path,
        doctor_id: int,
        target_date: date,
        session: str | None = None,
    ) -> list[dict[str, Any]]:
        conditions = [
            "status = 'waiting'",
            "doctor_id = ?",
            "preferred_date = ?",
        ]
        params: list[Any] = [doctor_id, target_date.isoformat()]

        if session:
            conditions.append("(preferred_session IS NULL OR preferred_session = ?)")
            params.append(session)

        where = " AND ".join(conditions)

        with get_db(db_path) as conn:
            rows = conn.execute(
                f"SELECT * FROM waitlist WHERE {where} ORDER BY priority DESC, created_at ASC",  # noqa: S608
                params,
            ).fetchall()
        return [dict(r) for r in rows]
