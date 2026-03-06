"""Reminder scheduling for document deadlines."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

from openclaw_shared.database import get_db


def get_reminders_due(
    db_path: Any,
    reminder_intervals: list[int] | None = None,
) -> list[dict]:
    """Return documents that need a reminder sent today.

    Checks each outstanding document against the reminder intervals (days before
    deadline). Skips documents that already had a reminder sent today.

    Args:
        db_path: Path to the client_portal database.
        reminder_intervals: Days before deadline to send reminders. Defaults to [7, 3, 1].

    Returns:
        List of dicts, each containing document info plus a 'days_until_deadline' field.
    """
    if reminder_intervals is None:
        reminder_intervals = [7, 3, 1]

    today = date.today()
    today_iso = today.isoformat()
    results: list[dict] = []

    with get_db(db_path) as conn:
        rows = conn.execute(
            """SELECT od.*, c.reference_code, c.client_name, c.client_phone,
                      c.client_telegram_id, c.language_pref, c.scheme
               FROM outstanding_documents od
               JOIN cases c ON c.id = od.case_id
               WHERE od.received = 0 AND od.deadline >= ?
               ORDER BY od.deadline ASC""",
            (today_iso,),
        ).fetchall()

    for row in rows:
        doc = dict(row)
        deadline = date.fromisoformat(doc["deadline"])
        days_until = (deadline - today).days

        if days_until not in reminder_intervals:
            continue

        last_sent = doc.get("last_reminder_sent")
        if last_sent and last_sent.startswith(today_iso):
            continue

        doc["days_until_deadline"] = days_until
        results.append(doc)

    return results


def mark_reminder_sent(db_path: Any, document_id: int) -> None:
    """Update the last_reminder_sent timestamp for a document."""
    now = datetime.now().isoformat()
    with get_db(db_path) as conn:
        conn.execute(
            "UPDATE outstanding_documents SET last_reminder_sent = ? WHERE id = ?",
            (now, document_id),
        )
