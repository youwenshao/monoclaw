"""Guest reliability scoring: A/B/C/D based on completion ratio.

Phone-number-based identity with 24-month confidence decay.
"""

from __future__ import annotations

import logging
import math
from datetime import date, datetime, timedelta
from typing import Any

from openclaw_shared.database import get_db

logger = logging.getLogger("openclaw.fnb.no-show-shield.reliability")

DECAY_MONTHS = 24
MIN_BOOKINGS_FOR_EXTREME = 3

SCORE_THRESHOLDS = {
    "A": 0.90,
    "B": 0.70,
    "C": 0.50,
}

SCORE_NUMERIC = {"A": 4, "B": 3, "C": 2, "D": 1}


def _apply_decay(total: int, months_since_last: float) -> float:
    """Exponential decay: recent activity weighs more."""
    if months_since_last <= 0 or total <= 0:
        return float(total)
    decay_factor = math.exp(-0.03 * months_since_last)
    return total * decay_factor


def _months_since(ref_date: str | None) -> float:
    if not ref_date:
        return DECAY_MONTHS
    try:
        last = datetime.fromisoformat(ref_date).date()
    except (ValueError, TypeError):
        return DECAY_MONTHS
    delta = (date.today() - last).days
    return max(0, delta / 30.44)


def calculate_score(db_path: str, phone: str) -> str:
    """Calculate reliability score for a guest by phone number.

    Returns "A", "B", "C", or "D".
    - A = >90% completion rate
    - B = 70-90% (also default for <3 bookings)
    - C = 50-70%
    - D = <50%
    """
    with get_db(db_path) as conn:
        row = conn.execute(
            """SELECT total_bookings, completed, no_shows, late_cancellations, last_visit
               FROM guests WHERE phone = ?""",
            (phone,),
        ).fetchone()

    if not row:
        return "B"

    guest = dict(row)
    total = guest["total_bookings"] or 0
    completed = guest["completed"] or 0

    if total < MIN_BOOKINGS_FOR_EXTREME:
        return "B"

    months = _months_since(guest.get("last_visit"))
    effective_total = _apply_decay(total, months)
    effective_completed = _apply_decay(completed, months)

    if effective_total <= 0:
        return "B"

    ratio = effective_completed / effective_total

    if ratio >= SCORE_THRESHOLDS["A"]:
        return "A"
    elif ratio >= SCORE_THRESHOLDS["B"]:
        return "B"
    elif ratio >= SCORE_THRESHOLDS["C"]:
        return "C"
    else:
        return "D"


def update_guest_stats(
    db_path: str,
    phone: str,
    outcome: str,
) -> dict[str, Any]:
    """Update guest statistics after a booking outcome.

    Args:
        outcome: one of "completed", "no_show", "late_cancel"

    Returns the updated guest record.
    """
    if outcome not in ("completed", "no_show", "late_cancel"):
        raise ValueError(f"Invalid outcome: {outcome}")

    with get_db(db_path) as conn:
        row = conn.execute("SELECT * FROM guests WHERE phone = ?", (phone,)).fetchone()

        if not row:
            conn.execute(
                """INSERT INTO guests (phone, total_bookings, completed, no_shows,
                   late_cancellations, reliability_score)
                   VALUES (?, 0, 0, 0, 0, 'B')""",
                (phone,),
            )
            row = conn.execute("SELECT * FROM guests WHERE phone = ?", (phone,)).fetchone()

        guest = dict(row)

        updates = {"total_bookings": (guest["total_bookings"] or 0) + 1}
        if outcome == "completed":
            updates["completed"] = (guest["completed"] or 0) + 1
            updates["last_visit"] = date.today().isoformat()
        elif outcome == "no_show":
            updates["no_shows"] = (guest["no_shows"] or 0) + 1
        elif outcome == "late_cancel":
            updates["late_cancellations"] = (guest["late_cancellations"] or 0) + 1

        set_clause = ", ".join(f"{k} = ?" for k in updates)
        values = list(updates.values()) + [phone]
        conn.execute(f"UPDATE guests SET {set_clause} WHERE phone = ?", values)  # noqa: S608

    new_score = calculate_score(db_path, phone)

    with get_db(db_path) as conn:
        conn.execute(
            "UPDATE guests SET reliability_score = ? WHERE phone = ?",
            (new_score, phone),
        )
        updated = conn.execute("SELECT * FROM guests WHERE phone = ?", (phone,)).fetchone()

    return dict(updated)


def get_guest(db_path: str, phone: str) -> dict[str, Any] | None:
    """Fetch a guest record by phone."""
    with get_db(db_path) as conn:
        row = conn.execute("SELECT * FROM guests WHERE phone = ?", (phone,)).fetchone()
    return dict(row) if row else None


def list_guests(
    db_path: str,
    score_filter: str | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    """List guests, optionally filtered by reliability score."""
    with get_db(db_path) as conn:
        if score_filter:
            rows = conn.execute(
                "SELECT * FROM guests WHERE reliability_score = ? ORDER BY total_bookings DESC LIMIT ?",
                (score_filter, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM guests ORDER BY total_bookings DESC LIMIT ?",
                (limit,),
            ).fetchall()
    return [dict(r) for r in rows]


def override_score(db_path: str, phone: str, new_score: str, reason: str = "") -> bool:
    """Manually override a guest's reliability score."""
    if new_score not in ("A", "B", "C", "D"):
        raise ValueError(f"Invalid score: {new_score}")

    with get_db(db_path) as conn:
        cursor = conn.execute(
            "UPDATE guests SET reliability_score = ? WHERE phone = ?",
            (new_score, phone),
        )
    return cursor.rowcount > 0
