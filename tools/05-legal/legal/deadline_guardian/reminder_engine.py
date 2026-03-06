"""Reminder scheduling and management for DeadlineGuardian.

Creates, queries, and updates reminder records in the ``reminders``
table.  Designed to be driven by an APScheduler job that periodically
calls :func:`get_pending_reminders` and dispatches via the configured
channel (WhatsApp / e-mail / desktop).
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path

from openclaw_shared.database import get_db

DEFAULT_CHANNELS = ["email", "whatsapp"]
DEFAULT_INTERVALS = [30, 14, 7, 3, 1]


def schedule_reminders(
    deadline_id: int,
    due_date: date,
    intervals_days: list[int],
    db_path: str | Path,
    channels: list[str] | None = None,
) -> list[int]:
    """Insert reminder rows for each *interval × channel* combination.

    Reminders whose computed date is already in the past are silently
    skipped.  Returns the list of newly created reminder IDs.
    """
    channels = channels or DEFAULT_CHANNELS
    created_ids: list[int] = []

    with get_db(db_path) as conn:
        for interval in sorted(intervals_days, reverse=True):
            reminder_date = due_date - timedelta(days=interval)
            if reminder_date < date.today():
                continue
            for channel in channels:
                cursor = conn.execute(
                    """INSERT INTO reminders
                       (deadline_id, reminder_date, channel, sent_status)
                       VALUES (?, ?, ?, 'pending')""",
                    (deadline_id, reminder_date.isoformat(), channel),
                )
                created_ids.append(cursor.lastrowid)

    return created_ids


def get_pending_reminders(db_path: str | Path) -> list[dict]:
    """Return all reminders that are due today or earlier and not yet sent.

    Joins through ``deadlines`` → ``cases`` so the caller has enough
    context to format a notification without extra queries.
    """
    today = date.today().isoformat()
    with get_db(db_path) as conn:
        rows = conn.execute(
            """SELECT r.*,
                      d.deadline_type, d.description AS deadline_description,
                      d.due_date, d.case_id,
                      c.case_number, c.case_name, c.solicitor_responsible
               FROM reminders r
               JOIN deadlines d ON r.deadline_id = d.id
               JOIN cases c ON d.case_id = c.id
               WHERE r.sent_status = 'pending'
                 AND r.reminder_date <= ?
                 AND d.status != 'completed'
               ORDER BY r.reminder_date ASC""",
            (today,),
        ).fetchall()
    return [dict(r) for r in rows]


def mark_reminder_sent(reminder_id: int, db_path: str | Path) -> None:
    """Set ``sent_status`` to ``'sent'`` for a single reminder."""
    with get_db(db_path) as conn:
        conn.execute(
            "UPDATE reminders SET sent_status = 'sent' WHERE id = ?",
            (reminder_id,),
        )


def acknowledge_reminder(
    reminder_id: int,
    acknowledged_by: str,
    db_path: str | Path,
) -> None:
    """Record that a human has acknowledged receipt of a reminder."""
    with get_db(db_path) as conn:
        conn.execute(
            """UPDATE reminders
               SET acknowledged = 1, acknowledged_by = ?, acknowledged_at = ?
               WHERE id = ?""",
            (acknowledged_by, datetime.now().isoformat(), reminder_id),
        )


def get_overdue_deadlines(db_path: str | Path) -> list[dict]:
    """Return all deadlines past their due date that are still open."""
    today = date.today().isoformat()
    with get_db(db_path) as conn:
        rows = conn.execute(
            """SELECT d.*, c.case_number, c.case_name, c.solicitor_responsible
               FROM deadlines d
               JOIN cases c ON d.case_id = c.id
               WHERE d.due_date < ? AND d.status NOT IN ('completed', 'waived')
               ORDER BY d.due_date ASC""",
            (today,),
        ).fetchall()
    return [dict(r) for r in rows]


def update_deadline_statuses(db_path: str | Path) -> int:
    """Bulk-refresh status flags on active deadlines.

    * Past-due → ``'overdue'``
    * Within 7 days → ``'due_soon'``

    Returns the total number of rows updated.
    """
    today = date.today().isoformat()
    seven_days = (date.today() + timedelta(days=7)).isoformat()
    updated = 0

    with get_db(db_path) as conn:
        updated += conn.execute(
            """UPDATE deadlines SET status = 'overdue'
               WHERE due_date < ?
                 AND status NOT IN ('completed', 'waived', 'overdue')""",
            (today,),
        ).rowcount
        updated += conn.execute(
            """UPDATE deadlines SET status = 'due_soon'
               WHERE due_date >= ? AND due_date <= ?
                 AND status NOT IN ('completed', 'waived', 'overdue', 'due_soon')""",
            (today, seven_days),
        ).rowcount

    return updated
