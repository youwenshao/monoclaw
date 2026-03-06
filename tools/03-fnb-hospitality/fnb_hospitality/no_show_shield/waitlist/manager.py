"""Priority-ranked waitlist per time slot with party-size and time-flexibility matching."""

from __future__ import annotations

import logging
from datetime import date, datetime, time, timedelta
from typing import Any

from openclaw_shared.database import get_db
from openclaw_shared.mona_events import emit_event

logger = logging.getLogger("openclaw.fnb.no-show-shield.waitlist")

PARTY_SIZE_TOLERANCE = 1
DEFAULT_FLEXIBILITY_MINUTES = 30


def add_to_waitlist(
    db_path: str,
    guest_name: str,
    guest_phone: str,
    party_size: int,
    preferred_date: str,
    preferred_time: str,
    flexibility_minutes: int = DEFAULT_FLEXIBILITY_MINUTES,
) -> int:
    """Add a guest to the waitlist. Returns the waitlist entry ID."""
    with get_db(db_path) as conn:
        cursor = conn.execute(
            """INSERT INTO waitlist
               (guest_name, guest_phone, party_size, preferred_date,
                preferred_time, flexibility_minutes, status)
               VALUES (?, ?, ?, ?, ?, ?, 'waiting')""",
            (guest_name, guest_phone, party_size, preferred_date,
             preferred_time, flexibility_minutes),
        )
        entry_id = cursor.lastrowid

    emit_event(
        db_path,
        event_type="info",
        tool_name="no-show-shield",
        summary=f"Waitlist: {guest_name} added for {preferred_date} {preferred_time} ({party_size} pax)",
    )

    logger.info("Added waitlist entry #%d: %s, %d pax", entry_id, guest_name, party_size)
    return entry_id  # type: ignore[return-value]


def get_waitlist(
    db_path: str,
    target_date: str | None = None,
    status: str = "waiting",
) -> list[dict[str, Any]]:
    """Retrieve waitlist entries, optionally filtered by date."""
    with get_db(db_path) as conn:
        if target_date:
            rows = conn.execute(
                """SELECT * FROM waitlist
                   WHERE preferred_date = ? AND status = ?
                   ORDER BY created_at ASC""",
                (target_date, status),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM waitlist WHERE status = ? ORDER BY created_at ASC",
                (status,),
            ).fetchall()
    return [dict(r) for r in rows]


def find_matching_entries(
    db_path: str,
    available_date: str,
    available_time: str,
    available_party_size: int,
) -> list[dict[str, Any]]:
    """Find waitlist entries matching an available slot.

    Matches by:
    - Party size within ±1 of available_party_size
    - Preferred date matches available_date
    - Preferred time within ±flexibility_minutes of available_time
    - Status is 'waiting'

    Results are ranked by priority: exact party size first, then by creation time.
    """
    avail_time = _parse_time(available_time)

    with get_db(db_path) as conn:
        rows = conn.execute(
            """SELECT * FROM waitlist
               WHERE preferred_date = ?
                 AND status = 'waiting'
                 AND party_size BETWEEN ? AND ?
               ORDER BY created_at ASC""",
            (
                available_date,
                available_party_size - PARTY_SIZE_TOLERANCE,
                available_party_size + PARTY_SIZE_TOLERANCE,
            ),
        ).fetchall()

    candidates = []
    for row in rows:
        entry = dict(row)
        pref_time = _parse_time(entry["preferred_time"])
        flex = timedelta(minutes=entry.get("flexibility_minutes", DEFAULT_FLEXIBILITY_MINUTES))

        time_diff = abs(_time_diff_minutes(avail_time, pref_time))
        if time_diff <= flex.total_seconds() / 60:
            entry["_size_diff"] = abs(entry["party_size"] - available_party_size)
            entry["_time_diff"] = time_diff
            candidates.append(entry)

    candidates.sort(key=lambda e: (e["_size_diff"], e["_time_diff"], e["id"]))

    for c in candidates:
        c.pop("_size_diff", None)
        c.pop("_time_diff", None)

    return candidates


def update_waitlist_status(
    db_path: str,
    entry_id: int,
    status: str,
    offered_booking_id: int | None = None,
) -> bool:
    """Update a waitlist entry status. Returns True if updated."""
    with get_db(db_path) as conn:
        if offered_booking_id is not None:
            conn.execute(
                "UPDATE waitlist SET status = ?, offered_booking_id = ? WHERE id = ?",
                (status, offered_booking_id, entry_id),
            )
        else:
            conn.execute(
                "UPDATE waitlist SET status = ? WHERE id = ?",
                (status, entry_id),
            )
    return True


def expire_old_entries(db_path: str, before_date: str | None = None) -> int:
    """Mark past-date waitlist entries as expired. Returns count expired."""
    cutoff = before_date or date.today().isoformat()
    with get_db(db_path) as conn:
        cursor = conn.execute(
            """UPDATE waitlist SET status = 'expired'
               WHERE preferred_date < ? AND status = 'waiting'""",
            (cutoff,),
        )
        return cursor.rowcount


def _parse_time(t: str | time) -> time:
    if isinstance(t, time):
        return t
    try:
        return datetime.strptime(t, "%H:%M").time()
    except ValueError:
        return datetime.strptime(t, "%H:%M:%S").time()


def _time_diff_minutes(t1: time, t2: time) -> float:
    d1 = timedelta(hours=t1.hour, minutes=t1.minute, seconds=t1.second)
    d2 = timedelta(hours=t2.hour, minutes=t2.minute, seconds=t2.second)
    return (d1 - d2).total_seconds() / 60
