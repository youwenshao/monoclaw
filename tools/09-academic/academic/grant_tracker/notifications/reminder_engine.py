"""Deadline reminder scheduling – check upcoming deadlines and trigger notifications."""

from __future__ import annotations

import logging
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Callable

from openclaw_shared.database import get_db

logger = logging.getLogger("openclaw.academic.grant_tracker.notifications.reminders")


def check_and_send_reminders(
    db_path: str | Path,
    reminder_days: list[int],
    send_fn: Callable[[dict, int], Any],
) -> list[dict]:
    """Check deadlines and trigger reminders for those within *reminder_days*.

    For each upcoming deadline whose days-remaining matches one of
    *reminder_days*, calls ``send_fn(deadline_dict, days_remaining)``.

    Args:
        db_path: Path to the grant_tracker database.
        reminder_days: List of day thresholds (e.g. [30, 14, 7, 3, 1]).
        send_fn: Callback that receives (deadline_dict, days_remaining).
                 Should handle the actual notification dispatch.

    Returns:
        List of dicts describing sent reminders: {deadline, days_remaining, sent}.
    """
    today = date.today()
    max_ahead = max(reminder_days) if reminder_days else 0
    cutoff = (today + timedelta(days=max_ahead)).isoformat()
    today_iso = today.isoformat()

    with get_db(db_path) as conn:
        rows = conn.execute(
            """SELECT d.*, gs.scheme_name, gs.scheme_code, gs.agency,
                      r.name_en AS pi_name, r.email AS pi_email
               FROM deadlines d
               JOIN grant_schemes gs ON gs.id = d.scheme_id
               LEFT JOIN applications a ON a.deadline_id = d.id
               LEFT JOIN researchers r ON r.id = a.researcher_id
               WHERE d.external_deadline >= ? AND d.external_deadline <= ?
                 AND d.status IN ('upcoming', 'open')
               ORDER BY d.external_deadline ASC""",
            (today_iso, cutoff),
        ).fetchall()

    sent_reminders: list[dict] = []
    for row in rows:
        dl = dict(row)
        ext_deadline = dl.get("external_deadline")
        if not ext_deadline:
            continue

        try:
            dl_date = date.fromisoformat(ext_deadline)
        except ValueError:
            continue

        days_remaining = (dl_date - today).days
        if days_remaining not in reminder_days:
            continue

        try:
            send_fn(dl, days_remaining)
            sent_reminders.append({
                "deadline": dl,
                "days_remaining": days_remaining,
                "sent": True,
            })
            logger.info(
                "Sent reminder for %s (deadline %s, %d days)",
                dl.get("scheme_code"), ext_deadline, days_remaining,
            )
        except Exception:
            logger.exception(
                "Failed to send reminder for %s (deadline %s)",
                dl.get("scheme_code"), ext_deadline,
            )
            sent_reminders.append({
                "deadline": dl,
                "days_remaining": days_remaining,
                "sent": False,
            })

    return sent_reminders


def format_reminder_message(deadline: dict, days_remaining: int) -> str:
    """Format a human-readable reminder message for a deadline.

    Example output::

        ⏰ Grant Deadline Reminder
        Scheme: GRF – General Research Fund (RGC)
        External deadline: 2025-11-15 (7 days remaining)
        Institutional deadline: 2025-10-25
        URL: https://...
    """
    scheme = deadline.get("scheme_code", "Unknown")
    name = deadline.get("scheme_name", "")
    agency = deadline.get("agency", "")
    ext_dl = deadline.get("external_deadline", "N/A")
    inst_dl = deadline.get("institutional_deadline", "N/A")
    url = deadline.get("call_url", "")

    urgency = "URGENT: " if days_remaining <= 3 else ""

    lines = [
        f"{urgency}Grant Deadline Reminder",
        f"Scheme: {scheme} – {name} ({agency})",
        f"External deadline: {ext_dl} ({days_remaining} day{'s' if days_remaining != 1 else ''} remaining)",
    ]

    if inst_dl and inst_dl != "N/A":
        lines.append(f"Institutional deadline: {inst_dl}")

    if url:
        lines.append(f"Details: {url}")

    notes = deadline.get("notes")
    if notes:
        lines.append(f"Notes: {notes}")

    return "\n".join(lines)
