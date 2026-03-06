"""Queue state machine: waiting -> notified -> seated / left.

FIFO ordering with grace queue for missed calls and typhoon T8+ auto-clear.
"""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

from openclaw_shared.database import get_db

HK_PHONE_RE = re.compile(r"^\+852[5679]\d{7}$")


def next_queue_number(db_path: str | Path) -> int:
    """Return the next queue number for today, resetting daily."""
    today = datetime.now().strftime("%Y-%m-%d")
    with get_db(db_path) as conn:
        row = conn.execute(
            "SELECT MAX(queue_number) FROM queue_entries WHERE DATE(joined_at) = ?",
            (today,),
        ).fetchone()
    return (row[0] or 0) + 1


def join_queue(
    db_path: str | Path,
    guest_name: str,
    guest_phone: str,
    party_size: int,
    seating_preference: str | None = None,
    language_pref: str = "zh",
    channel: str = "qr",
    estimated_wait: int | None = None,
) -> dict:
    """Add a guest to the queue and return the new entry as a dict."""
    if not HK_PHONE_RE.match(guest_phone):
        raise ValueError(f"Invalid HK phone number: {guest_phone}")
    if party_size < 1:
        raise ValueError("Party size must be at least 1")

    q_num = next_queue_number(db_path)

    with get_db(db_path) as conn:
        position = conn.execute(
            "SELECT COUNT(*) FROM queue_entries WHERE status IN ('waiting', 'notified')",
        ).fetchone()[0] + 1

        cursor = conn.execute(
            """INSERT INTO queue_entries
               (queue_number, guest_name, guest_phone, party_size,
                seating_preference, status, estimated_wait_minutes,
                position_at_join, channel)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (q_num, guest_name, guest_phone, party_size,
             seating_preference, "waiting", estimated_wait, position, channel),
        )
        entry_id = cursor.lastrowid
        row = conn.execute(
            "SELECT * FROM queue_entries WHERE id = ?", (entry_id,),
        ).fetchone()

    return dict(row)


def call_next(db_path: str | Path) -> dict | None:
    """Move the next waiting entry to 'notified'. Returns the entry or None."""
    now = datetime.now().isoformat()
    with get_db(db_path) as conn:
        row = conn.execute(
            """SELECT * FROM queue_entries
               WHERE status = 'waiting'
               ORDER BY joined_at ASC LIMIT 1""",
        ).fetchone()
        if not row:
            return None
        entry = dict(row)
        conn.execute(
            "UPDATE queue_entries SET status = 'notified', notified_at = ? WHERE id = ?",
            (now, entry["id"]),
        )
        entry["status"] = "notified"
        entry["notified_at"] = now
    return entry


def seat_guest(db_path: str | Path, queue_id: int) -> dict:
    """Mark a queue entry as seated and compute actual wait time."""
    now = datetime.now()
    with get_db(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM queue_entries WHERE id = ?", (queue_id,),
        ).fetchone()
        if not row:
            raise ValueError(f"Queue entry {queue_id} not found")
        entry = dict(row)
        if entry["status"] not in ("waiting", "notified"):
            raise ValueError(f"Cannot seat entry with status '{entry['status']}'")

        joined = datetime.fromisoformat(entry["joined_at"])
        actual_wait = int((now - joined).total_seconds() / 60)

        conn.execute(
            """UPDATE queue_entries
               SET status = 'seated', seated_at = ?, actual_wait_minutes = ?
               WHERE id = ?""",
            (now.isoformat(), actual_wait, queue_id),
        )
        entry["status"] = "seated"
        entry["seated_at"] = now.isoformat()
        entry["actual_wait_minutes"] = actual_wait
    return entry


def mark_left(db_path: str | Path, queue_id: int) -> dict:
    """Mark a queue entry as left (walkout)."""
    now = datetime.now()
    with get_db(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM queue_entries WHERE id = ?", (queue_id,),
        ).fetchone()
        if not row:
            raise ValueError(f"Queue entry {queue_id} not found")
        entry = dict(row)
        if entry["status"] not in ("waiting", "notified"):
            raise ValueError(f"Cannot mark left for status '{entry['status']}'")

        joined = datetime.fromisoformat(entry["joined_at"])
        actual_wait = int((now - joined).total_seconds() / 60)

        conn.execute(
            """UPDATE queue_entries
               SET status = 'left', left_at = ?, actual_wait_minutes = ?
               WHERE id = ?""",
            (now.isoformat(), actual_wait, queue_id),
        )
        entry["status"] = "left"
        entry["left_at"] = now.isoformat()
        entry["actual_wait_minutes"] = actual_wait
    return entry


def skip_guest(db_path: str | Path, queue_id: int) -> dict:
    """Move a notified/waiting guest to the back of the FIFO (grace queue)."""
    with get_db(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM queue_entries WHERE id = ?", (queue_id,),
        ).fetchone()
        if not row:
            raise ValueError(f"Queue entry {queue_id} not found")
        entry = dict(row)
        if entry["status"] not in ("waiting", "notified"):
            raise ValueError(f"Cannot skip entry with status '{entry['status']}'")

        conn.execute(
            """UPDATE queue_entries
               SET status = 'waiting', notified_at = NULL,
                   joined_at = CURRENT_TIMESTAMP
               WHERE id = ?""",
            (queue_id,),
        )
        updated = conn.execute(
            "SELECT * FROM queue_entries WHERE id = ?", (queue_id,),
        ).fetchone()
    return dict(updated)


def remove_guest(db_path: str | Path, queue_id: int) -> dict:
    """Remove a guest from the queue entirely."""
    with get_db(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM queue_entries WHERE id = ?", (queue_id,),
        ).fetchone()
        if not row:
            raise ValueError(f"Queue entry {queue_id} not found")
        entry = dict(row)
        conn.execute(
            "UPDATE queue_entries SET status = 'removed' WHERE id = ?",
            (queue_id,),
        )
        entry["status"] = "removed"
    return entry


def get_active_queue(db_path: str | Path) -> list[dict]:
    """Return all waiting and notified entries in FIFO order.

    Notified entries appear first, then waiting entries ordered by join time.
    """
    with get_db(db_path) as conn:
        rows = conn.execute(
            """SELECT * FROM queue_entries
               WHERE status IN ('waiting', 'notified')
               ORDER BY
                 CASE status WHEN 'notified' THEN 0 ELSE 1 END,
                 joined_at ASC""",
        ).fetchall()
    return [dict(r) for r in rows]


def get_queue_position(db_path: str | Path, queue_id: int) -> int | None:
    """Return 1-based queue position for a given entry, or None if not active."""
    active = get_active_queue(db_path)
    for i, entry in enumerate(active):
        if entry["id"] == queue_id:
            return i + 1
    return None


def typhoon_clear(db_path: str | Path) -> int:
    """Clear all waiting/notified entries due to T8+ typhoon signal.

    Returns count of entries cleared.
    """
    now = datetime.now().isoformat()
    with get_db(db_path) as conn:
        result = conn.execute(
            """UPDATE queue_entries
               SET status = 'left', left_at = ?
               WHERE status IN ('waiting', 'notified')""",
            (now,),
        )
    return result.rowcount
