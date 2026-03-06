"""Available time-slot calculator for property viewings."""

from __future__ import annotations

from datetime import datetime, date, time, timedelta
from pathlib import Path
from typing import Any

from openclaw_shared.database import get_db

SLOT_DURATION_MINUTES = 30


def _time_range(start_str: str, end_str: str, step_min: int = SLOT_DURATION_MINUTES) -> list[tuple[time, time]]:
    """Generate (start, end) time pairs covering a range in fixed increments."""
    start = datetime.strptime(start_str, "%H:%M").time()
    end = datetime.strptime(end_str, "%H:%M").time()
    slots: list[tuple[time, time]] = []

    current = datetime.combine(date.today(), start)
    limit = datetime.combine(date.today(), end)
    while current + timedelta(minutes=step_min) <= limit:
        slot_start = current.time()
        slot_end = (current + timedelta(minutes=step_min)).time()
        slots.append((slot_start, slot_end))
        current += timedelta(minutes=step_min)

    return slots


def get_available_slots(
    db_path: str | Path,
    property_ref: str,
    target_date: date,
    viewing_hours: tuple[str, str] = ("10:00", "20:00"),
) -> list[dict[str, Any]]:
    """Return time slots for a property on a given date with availability flags.

    Checks the availability_windows table for landlord-defined hours and
    cross-references existing bookings to mark occupied slots.
    """
    day_of_week = target_date.weekday()  # 0=Monday

    with get_db(db_path) as conn:
        windows = conn.execute(
            """SELECT start_time, end_time, landlord_blackout_dates
               FROM availability_windows
               WHERE property_ref = ? AND day_of_week = ?""",
            (property_ref, day_of_week),
        ).fetchall()

        bookings = conn.execute(
            """SELECT proposed_datetime, confirmed_datetime
               FROM viewings
               WHERE property_ref = ?
                 AND status NOT IN ('cancelled')
                 AND DATE(COALESCE(confirmed_datetime, proposed_datetime)) = ?""",
            (property_ref, target_date.isoformat()),
        ).fetchall()

    if windows:
        window = dict(windows[0])
        blackout_raw = window.get("landlord_blackout_dates") or ""
        blackout_dates = [d.strip() for d in blackout_raw.split(",") if d.strip()]
        if target_date.isoformat() in blackout_dates:
            return [{"start": s.isoformat(), "end": e.isoformat(), "available": False}
                    for s, e in _time_range(viewing_hours[0], viewing_hours[1])]

        start_str = window.get("start_time") or viewing_hours[0]
        end_str = window.get("end_time") or viewing_hours[1]
    else:
        start_str, end_str = viewing_hours

    booked_times: set[time] = set()
    for b in bookings:
        dt_str = b["confirmed_datetime"] or b["proposed_datetime"]
        try:
            dt = datetime.fromisoformat(dt_str)
            booked_times.add(dt.time().replace(second=0, microsecond=0))
        except (ValueError, TypeError):
            continue

    all_slots = _time_range(start_str, end_str)
    result: list[dict[str, Any]] = []
    for slot_start, slot_end in all_slots:
        available = slot_start not in booked_times
        result.append({
            "start": slot_start.isoformat(),
            "end": slot_end.isoformat(),
            "available": available,
        })

    return result
