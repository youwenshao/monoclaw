"""Booking conflict detection, slot suggestion, and capacity checks."""

from __future__ import annotations

import logging
from datetime import date, datetime, time, timedelta
from typing import Any

from openclaw_shared.database import get_db

logger = logging.getLogger("openclaw.table_master.booking.engine")

MEAL_DURATIONS: dict[str, int] = {
    "lunch": 75,
    "dinner_weekday": 90,
    "dinner_weekend": 120,
    "dim_sum": 120,
}

MEAL_WINDOWS: dict[str, tuple[time, time]] = {
    "lunch": (time(12, 0), time(14, 0)),
    "dinner_weekday": (time(19, 0), time(21, 30)),
    "dinner_weekend": (time(19, 0), time(21, 30)),
    "dim_sum": (time(10, 0), time(14, 30)),
}


def infer_meal_type(booking_time: str, booking_date: str) -> str:
    """Determine meal type from time and date to get the correct duration."""
    t = _parse_time(booking_time)
    d = _parse_date(booking_date)

    if time(10, 0) <= t < time(11, 30):
        return "dim_sum"
    if time(11, 30) <= t < time(15, 0):
        return "lunch"

    is_weekend = d.weekday() >= 5
    return "dinner_weekend" if is_weekend else "dinner_weekday"


def get_dining_duration(meal_type: str) -> int:
    """Return expected dining duration in minutes for the given meal type."""
    return MEAL_DURATIONS.get(meal_type, 90)


def compute_end_time(booking_time: str, booking_date: str) -> str:
    """Compute the expected end time as HH:MM given booking time and date."""
    meal = infer_meal_type(booking_time, booking_date)
    duration = get_dining_duration(meal)
    t = _parse_time(booking_time)
    dt = datetime.combine(date.today(), t) + timedelta(minutes=duration)
    return dt.strftime("%H:%M")


def detect_conflicts(
    db_path: str,
    table_id: int,
    booking_date: str,
    booking_time: str,
    *,
    duration_minutes: int | None = None,
    exclude_booking_id: int | None = None,
) -> list[dict[str, Any]]:
    """Check for overlapping bookings on the same table.

    Returns a list of conflict dicts.  An empty list means no conflicts.
    """
    if duration_minutes is None:
        meal = infer_meal_type(booking_time, booking_date)
        duration_minutes = get_dining_duration(meal)

    start = _parse_time(booking_time)
    end_dt = datetime.combine(date.today(), start) + timedelta(minutes=duration_minutes)
    end = end_dt.time()

    conflicts: list[dict[str, Any]] = []

    with get_db(db_path) as conn:
        query = """
            SELECT id, guest_name, booking_time, end_time, party_size, status
            FROM bookings
            WHERE table_id = ?
              AND booking_date = ?
              AND status IN ('pending', 'confirmed')
        """
        params: list[Any] = [table_id, booking_date]

        if exclude_booking_id is not None:
            query += " AND id != ?"
            params.append(exclude_booking_id)

        rows = conn.execute(query, params).fetchall()

        for row in rows:
            existing = dict(row)
            ex_start = _parse_time(existing["booking_time"])

            if existing.get("end_time"):
                ex_end = _parse_time(existing["end_time"])
            else:
                ex_meal = infer_meal_type(existing["booking_time"], booking_date)
                ex_dur = get_dining_duration(ex_meal)
                ex_end = (datetime.combine(date.today(), ex_start) + timedelta(minutes=ex_dur)).time()

            if start < ex_end and end > ex_start:
                conflicts.append({
                    "booking_id": existing["id"],
                    "guest_name": existing["guest_name"],
                    "time_range": f"{ex_start.strftime('%H:%M')}-{ex_end.strftime('%H:%M')}",
                    "party_size": existing["party_size"],
                    "severity": "error",
                    "detail": (
                        f"Overlaps with booking #{existing['id']} "
                        f"({existing['guest_name']}, {ex_start.strftime('%H:%M')}-{ex_end.strftime('%H:%M')})"
                    ),
                })

    return conflicts


def suggest_nearest_slot(
    db_path: str,
    table_id: int,
    booking_date: str,
    booking_time: str,
    *,
    window_minutes: int = 30,
    step_minutes: int = 15,
) -> list[dict[str, str]]:
    """Suggest the nearest available time slots within ±window_minutes.

    Returns a list of ``{"time": "HH:MM", "end_time": "HH:MM"}`` dicts
    sorted by distance from the requested time.
    """
    meal = infer_meal_type(booking_time, booking_date)
    duration = get_dining_duration(meal)
    base = _parse_time(booking_time)
    base_dt = datetime.combine(date.today(), base)

    candidates: list[tuple[int, str]] = []
    for offset in range(-window_minutes, window_minutes + 1, step_minutes):
        if offset == 0:
            continue
        candidate_dt = base_dt + timedelta(minutes=offset)
        candidate_time = candidate_dt.strftime("%H:%M")

        with get_db(db_path) as conn:
            row = conn.execute(
                """SELECT id FROM bookings
                   WHERE table_id = ? AND booking_date = ?
                     AND status IN ('pending', 'confirmed')""",
                (table_id, booking_date),
            ).fetchone()

        conflicts = detect_conflicts(
            db_path, table_id, booking_date, candidate_time, duration_minutes=duration,
        )
        if not conflicts:
            end_dt = candidate_dt + timedelta(minutes=duration)
            candidates.append((abs(offset), candidate_time))

    candidates.sort(key=lambda x: x[0])

    suggestions = []
    for _, t in candidates:
        end = (datetime.combine(date.today(), _parse_time(t)) + timedelta(minutes=duration)).strftime("%H:%M")
        suggestions.append({"time": t, "end_time": end})

    return suggestions


def check_capacity(
    db_path: str,
    party_size: int,
    booking_date: str,
    booking_time: str,
) -> dict[str, Any]:
    """Check whether any table can accommodate the party at the requested time.

    Returns a dict with ``available`` bool, matching ``table_ids``, and
    ``suggestions`` if no exact match is found.
    """
    meal = infer_meal_type(booking_time, booking_date)
    duration = get_dining_duration(meal)

    with get_db(db_path) as conn:
        tables = [dict(r) for r in conn.execute(
            "SELECT * FROM tables WHERE status = 'available' ORDER BY seats ASC"
        ).fetchall()]

    direct_matches: list[dict[str, Any]] = []
    combo_matches: list[dict[str, Any]] = []

    for table in tables:
        if table["seats"] >= party_size:
            conflicts = detect_conflicts(
                db_path, table["id"], booking_date, booking_time, duration_minutes=duration,
            )
            if not conflicts:
                direct_matches.append(table)

    if not direct_matches:
        combo_matches = _find_combinable(tables, party_size, db_path, booking_date, booking_time, duration)

    available = bool(direct_matches) or bool(combo_matches)
    return {
        "available": available,
        "direct_tables": [t["id"] for t in direct_matches],
        "combo_tables": combo_matches,
        "party_size": party_size,
        "meal_type": meal,
        "duration_minutes": duration,
    }


def _find_combinable(
    tables: list[dict[str, Any]],
    party_size: int,
    db_path: str,
    booking_date: str,
    booking_time: str,
    duration: int,
) -> list[dict[str, Any]]:
    """Find pairs of combinable tables that together fit the party."""
    combos: list[dict[str, Any]] = []
    seen: set[tuple[int, int]] = set()

    for table in tables:
        if not table.get("is_combinable") or not table.get("combine_with"):
            continue

        partner_num = table["combine_with"]
        partner = next((t for t in tables if t["table_number"] == partner_num), None)
        if not partner:
            continue

        pair = tuple(sorted([table["id"], partner["id"]]))
        if pair in seen:
            continue
        seen.add(pair)

        combined_seats = table["seats"] + partner["seats"]
        if combined_seats < party_size:
            continue

        conflicts_a = detect_conflicts(db_path, table["id"], booking_date, booking_time, duration_minutes=duration)
        conflicts_b = detect_conflicts(db_path, partner["id"], booking_date, booking_time, duration_minutes=duration)
        if not conflicts_a and not conflicts_b:
            combos.append({
                "table_ids": list(pair),
                "table_numbers": [table["table_number"], partner_num],
                "combined_seats": combined_seats,
            })

    return combos


def _parse_time(t: str) -> time:
    """Parse HH:MM or HH:MM:SS into a time object."""
    parts = t.strip().split(":")
    return time(int(parts[0]), int(parts[1]))


def _parse_date(d: str) -> date:
    """Parse YYYY-MM-DD into a date object."""
    return date.fromisoformat(d)
