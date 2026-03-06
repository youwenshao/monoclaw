"""Capacity calculator — accounts for combinable tables and dining
duration by meal type to give an accurate picture of how many covers
the restaurant can handle in a given service."""

from __future__ import annotations

import logging
from datetime import date, datetime, time, timedelta
from typing import Any

from openclaw_shared.database import get_db

from fnb_hospitality.table_master.booking.engine import (
    MEAL_DURATIONS,
    MEAL_WINDOWS,
    detect_conflicts,
    get_dining_duration,
    infer_meal_type,
)

logger = logging.getLogger("openclaw.table_master.inventory.capacity")


def calculate_service_capacity(
    db_path: str,
    target_date: str,
    meal_type: str,
    *,
    turnovers: int = 2,
) -> dict[str, Any]:
    """Calculate total covers for a service period.

    Considers:
    - Individual table seats
    - Combinable table pairs (counted once, at combined capacity)
    - Expected turnovers per service
    - Dining duration for the meal type
    """
    duration = get_dining_duration(meal_type)
    window = MEAL_WINDOWS.get(meal_type)

    with get_db(db_path) as conn:
        tables = [dict(r) for r in conn.execute(
            "SELECT * FROM tables WHERE status != 'maintenance' ORDER BY seats ASC"
        ).fetchall()]

    single_seats = 0
    combo_seats = 0
    combo_seen: set[tuple[int, int]] = set()

    for table in tables:
        if table.get("is_combinable") and table.get("combine_with"):
            partner = next(
                (t for t in tables if t["table_number"] == table["combine_with"]),
                None,
            )
            if partner:
                pair = tuple(sorted([table["id"], partner["id"]]))
                if pair not in combo_seen:
                    combo_seen.add(pair)
                    combo_seats += table["seats"] + partner["seats"]
                continue

        single_seats += table["seats"]

    total_seats = single_seats + combo_seats

    if window:
        window_start, window_end = window
        window_minutes = (
            datetime.combine(date.today(), window_end)
            - datetime.combine(date.today(), window_start)
        ).total_seconds() / 60
        max_turnovers = max(1, int(window_minutes / duration))
        effective_turnovers = min(turnovers, max_turnovers)
    else:
        effective_turnovers = turnovers

    max_covers = total_seats * effective_turnovers

    return {
        "date": target_date,
        "meal_type": meal_type,
        "total_tables": len(tables),
        "single_seats": single_seats,
        "combo_seats": combo_seats,
        "total_seats": total_seats,
        "turnovers": effective_turnovers,
        "dining_duration_minutes": duration,
        "max_covers": max_covers,
    }


def calculate_remaining_capacity(
    db_path: str,
    target_date: str,
    booking_time: str,
) -> dict[str, Any]:
    """Calculate remaining capacity at a specific time slot.

    Subtracts existing bookings from the total to show how many more
    covers can be accepted.
    """
    meal = infer_meal_type(booking_time, target_date)
    duration = get_dining_duration(meal)

    with get_db(db_path) as conn:
        tables = [dict(r) for r in conn.execute(
            "SELECT * FROM tables WHERE status != 'maintenance'"
        ).fetchall()]

        booked_rows = conn.execute(
            """SELECT table_id, party_size FROM bookings
               WHERE booking_date = ?
                 AND status IN ('pending', 'confirmed')""",
            (target_date,),
        ).fetchall()

    booked_table_ids: set[int] = set()
    booked_covers = 0

    for row in booked_rows:
        b = dict(row)
        if b["table_id"]:
            conflicts = detect_conflicts(
                db_path, b["table_id"], target_date, booking_time,
                duration_minutes=duration,
            )
            if conflicts or b["table_id"] in booked_table_ids:
                continue
            booked_table_ids.add(b["table_id"])
        booked_covers += b["party_size"]

    available_tables = [t for t in tables if t["id"] not in booked_table_ids]
    available_seats = sum(t["seats"] for t in available_tables)

    total_seats = sum(t["seats"] for t in tables)
    utilisation = (booked_covers / total_seats * 100) if total_seats else 0

    return {
        "date": target_date,
        "time": booking_time,
        "meal_type": meal,
        "total_tables": len(tables),
        "available_tables": len(available_tables),
        "total_seats": total_seats,
        "available_seats": available_seats,
        "booked_covers": booked_covers,
        "remaining_covers": available_seats,
        "utilisation_percent": round(utilisation, 1),
    }


def get_daily_capacity_overview(
    db_path: str,
    target_date: str,
) -> dict[str, Any]:
    """Return capacity overview for all meal types on a given date."""
    d = date.fromisoformat(target_date)
    is_weekend = d.weekday() >= 5

    services = ["dim_sum", "lunch"]
    services.append("dinner_weekend" if is_weekend else "dinner_weekday")

    overview: dict[str, Any] = {"date": target_date, "is_weekend": is_weekend, "services": {}}

    for meal in services:
        cap = calculate_service_capacity(db_path, target_date, meal)

        window = MEAL_WINDOWS.get(meal)
        mid_time = "12:30" if "lunch" in meal or meal == "dim_sum" else "19:30"
        if window:
            mid_dt = datetime.combine(
                date.today(), window[0]
            ) + timedelta(
                minutes=(
                    datetime.combine(date.today(), window[1])
                    - datetime.combine(date.today(), window[0])
                ).total_seconds() / 120,
            )
            mid_time = mid_dt.strftime("%H:%M")

        remaining = calculate_remaining_capacity(db_path, target_date, mid_time)

        overview["services"][meal] = {
            **cap,
            "booked_covers": remaining["booked_covers"],
            "remaining_covers": remaining["remaining_covers"],
            "utilisation_percent": remaining["utilisation_percent"],
        }

    return overview
