"""Walk-in patient queue for the ClinicScheduler."""

from __future__ import annotations

import logging
from datetime import date, datetime
from pathlib import Path
from typing import Any

from openclaw_shared.database import get_db

logger = logging.getLogger("openclaw.medical-dental.scheduler.walkin")

_WALK_IN_DDL = """
CREATE TABLE IF NOT EXISTS walk_in_queue (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    queue_number INTEGER NOT NULL,
    patient_name TEXT NOT NULL,
    patient_phone TEXT,
    service_type TEXT DEFAULT 'gp',
    status TEXT CHECK(status IN ('waiting','serving','completed','left')) DEFAULT 'waiting',
    joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    called_at TIMESTAMP,
    completed_at TIMESTAMP
);
"""

DEFAULT_SERVICE_MINUTES: dict[str, int] = {
    "gp": 15,
    "specialist": 30,
    "dental_cleaning": 45,
    "dental_procedure": 60,
    "follow_up": 15,
}


def _ensure_table(db_path: str | Path) -> None:
    with get_db(db_path) as conn:
        conn.executescript(_WALK_IN_DDL)


def _next_queue_number(conn: Any) -> int:
    today = date.today().isoformat()
    row = conn.execute(
        "SELECT MAX(queue_number) AS mx FROM walk_in_queue WHERE DATE(joined_at) = ?",
        (today,),
    ).fetchone()
    return (row["mx"] or 0) + 1


class WalkInQueue:
    """Manages a daily walk-in patient queue with estimated wait times."""

    def __init__(self, service_durations: dict[str, int] | None = None) -> None:
        self._durations = service_durations or DEFAULT_SERVICE_MINUTES

    def add_walk_in(
        self,
        db_path: str | Path,
        patient_name: str,
        patient_phone: str,
        service_type: str = "gp",
    ) -> dict[str, Any]:
        _ensure_table(db_path)

        with get_db(db_path) as conn:
            q_num = _next_queue_number(conn)
            conn.execute(
                """INSERT INTO walk_in_queue
                   (queue_number, patient_name, patient_phone, service_type, status)
                   VALUES (?,?,?,?,?)""",
                (q_num, patient_name, patient_phone, service_type, "waiting"),
            )

        est_wait = self.estimate_wait(db_path)

        logger.info("Walk-in #%d: %s (%s), est wait %d min", q_num, patient_name, service_type, est_wait)
        return {"queue_number": q_num, "estimated_wait": est_wait}

    def get_queue(self, db_path: str | Path) -> list[dict[str, Any]]:
        _ensure_table(db_path)
        today = date.today().isoformat()

        with get_db(db_path) as conn:
            rows = conn.execute(
                """SELECT * FROM walk_in_queue
                   WHERE DATE(joined_at) = ? AND status IN ('waiting', 'serving')
                   ORDER BY queue_number""",
                (today,),
            ).fetchall()
        return [dict(r) for r in rows]

    def call_next(self, db_path: str | Path) -> dict[str, Any] | None:
        _ensure_table(db_path)
        today = date.today().isoformat()

        with get_db(db_path) as conn:
            row = conn.execute(
                """SELECT * FROM walk_in_queue
                   WHERE DATE(joined_at) = ? AND status = 'waiting'
                   ORDER BY queue_number LIMIT 1""",
                (today,),
            ).fetchone()
            if not row:
                return None

            entry = dict(row)
            now = datetime.now().isoformat()
            conn.execute(
                "UPDATE walk_in_queue SET status = 'serving', called_at = ? WHERE id = ?",
                (now, entry["id"]),
            )
            entry["status"] = "serving"
            entry["called_at"] = now

        logger.info("Called walk-in #%d: %s", entry["queue_number"], entry["patient_name"])
        return entry

    def estimate_wait(self, db_path: str | Path) -> int:
        _ensure_table(db_path)
        today = date.today().isoformat()

        with get_db(db_path) as conn:
            rows = conn.execute(
                """SELECT service_type FROM walk_in_queue
                   WHERE DATE(joined_at) = ? AND status = 'waiting'""",
                (today,),
            ).fetchall()

        total = 0
        for row in rows:
            svc = row["service_type"] or "gp"
            total += self._durations.get(svc, 15)
        return total

    def get_display_data(self, db_path: str | Path) -> dict[str, Any]:
        _ensure_table(db_path)
        today = date.today().isoformat()

        with get_db(db_path) as conn:
            waiting = [dict(r) for r in conn.execute(
                """SELECT queue_number, patient_name, service_type, joined_at
                   FROM walk_in_queue
                   WHERE DATE(joined_at) = ? AND status = 'waiting'
                   ORDER BY queue_number""",
                (today,),
            ).fetchall()]

            serving = [dict(r) for r in conn.execute(
                """SELECT queue_number, patient_name, service_type, called_at
                   FROM walk_in_queue
                   WHERE DATE(joined_at) = ? AND status = 'serving'
                   ORDER BY called_at DESC""",
                (today,),
            ).fetchall()]

        return {
            "queue": waiting,
            "currently_serving": serving,
            "waiting_count": len(waiting),
        }
