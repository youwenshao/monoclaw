"""Interview scheduling and reminder management."""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

from openclaw_shared.database import get_db


def schedule_interview(
    application_id: int,
    interview_type: str,
    dt: str,
    location: str,
    db_path: str | Path,
) -> int:
    with get_db(db_path) as conn:
        app_row = conn.execute(
            "SELECT id FROM applications WHERE id = ?", (application_id,)
        ).fetchone()
        if not app_row:
            raise ValueError(f"Application {application_id} not found")

        cursor = conn.execute(
            """INSERT INTO interviews (application_id, interview_type, datetime, location)
               VALUES (?, ?, ?, ?)""",
            (application_id, interview_type, dt, location),
        )
        interview_id = cursor.lastrowid

        conn.execute(
            """UPDATE applications SET stage = 'interview'
               WHERE id = ? AND stage NOT IN ('offer', 'accepted', 'final_round')""",
            (application_id,),
        )

    return interview_id


def get_upcoming_interviews(db_path: str | Path, days_ahead: int = 30) -> list[dict]:
    cutoff = (datetime.now() + timedelta(days=days_ahead)).isoformat()
    now = datetime.now().isoformat()

    with get_db(db_path) as conn:
        rows = conn.execute(
            """SELECT i.*, a.job_id, a.stage, a.notes as app_notes,
                      j.title, j.company, j.location as job_location
               FROM interviews i
               JOIN applications a ON i.application_id = a.id
               LEFT JOIN job_listings j ON a.job_id = j.id
               WHERE i.datetime >= ? AND i.datetime <= ?
               ORDER BY i.datetime ASC""",
            (now, cutoff),
        ).fetchall()

    return [dict(r) for r in rows]


def check_reminders(db_path: str | Path, hours_before: int = 24) -> list[dict]:
    threshold = (datetime.now() + timedelta(hours=hours_before)).isoformat()
    now = datetime.now().isoformat()

    with get_db(db_path) as conn:
        rows = conn.execute(
            """SELECT i.*, j.title, j.company
               FROM interviews i
               JOIN applications a ON i.application_id = a.id
               LEFT JOIN job_listings j ON a.job_id = j.id
               WHERE i.datetime >= ? AND i.datetime <= ?
                 AND i.reminder_sent = 0""",
            (now, threshold),
        ).fetchall()

    return [dict(r) for r in rows]


def mark_reminder_sent(interview_id: int, db_path: str | Path) -> None:
    with get_db(db_path) as conn:
        conn.execute(
            "UPDATE interviews SET reminder_sent = 1 WHERE id = ?",
            (interview_id,),
        )
