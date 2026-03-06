"""Smart table assignment — party size fit, preference matching, section
balancing, and table combination logic."""

from __future__ import annotations

import logging
from typing import Any

from openclaw_shared.database import get_db

from fnb_hospitality.table_master.booking.engine import (
    detect_conflicts,
    get_dining_duration,
    infer_meal_type,
)

logger = logging.getLogger("openclaw.table_master.booking.assigner")

PREFERENCE_MAP: dict[str, list[str]] = {
    "window": ["window"],
    "window seat": ["window"],
    "quiet": ["quiet"],
    "quiet corner": ["quiet"],
    "booth": ["booth"],
    "private room": ["private_room"],
    "private": ["private_room"],
    "round table": ["round_table"],
}


def assign_table(
    db_path: str,
    booking_id: int,
    *,
    party_size: int,
    booking_date: str,
    booking_time: str,
    special_requests: str = "",
) -> dict[str, Any]:
    """Find the best table for a booking and assign it.

    Algorithm:
    1. Parse preferences from special_requests.
    2. Filter tables that fit party_size (direct or combined).
    3. Score by: preference match > smallest adequate table > section balance.
    4. Assign the top-scoring table and update both bookings and tables rows.

    Returns a dict with ``assigned``, ``table_id``, ``table_number``, etc.
    """
    meal = infer_meal_type(booking_time, booking_date)
    duration = get_dining_duration(meal)
    prefs = _parse_preferences(special_requests)

    with get_db(db_path) as conn:
        all_tables = [dict(r) for r in conn.execute(
            "SELECT * FROM tables ORDER BY seats ASC"
        ).fetchall()]

        section_counts = _count_section_bookings(conn, booking_date, booking_time)

    scored_singles: list[tuple[float, dict[str, Any]]] = []
    scored_combos: list[tuple[float, dict[str, Any]]] = []

    for table in all_tables:
        if table["seats"] < party_size:
            continue

        conflicts = detect_conflicts(
            db_path, table["id"], booking_date, booking_time,
            duration_minutes=duration, exclude_booking_id=booking_id,
        )
        if conflicts:
            continue

        score = _score_table(table, party_size, prefs, section_counts)
        scored_singles.append((score, table))

    if not scored_singles:
        combos = _find_combos(all_tables, party_size, db_path, booking_date, booking_time, duration)
        for combo in combos:
            score = _score_combo(combo, party_size, prefs, section_counts)
            scored_combos.append((score, combo))

    if scored_singles:
        scored_singles.sort(key=lambda x: x[0], reverse=True)
        best = scored_singles[0][1]
        return _assign_single(db_path, booking_id, best)

    if scored_combos:
        scored_combos.sort(key=lambda x: x[0], reverse=True)
        best_combo = scored_combos[0][1]
        return _assign_combo(db_path, booking_id, best_combo)

    return {
        "assigned": False,
        "reason": "No available table fits this booking",
        "party_size": party_size,
        "booking_id": booking_id,
    }


def _assign_single(db_path: str, booking_id: int, table: dict[str, Any]) -> dict[str, Any]:
    with get_db(db_path) as conn:
        conn.execute(
            "UPDATE bookings SET table_id = ? WHERE id = ?",
            (table["id"], booking_id),
        )
        conn.execute(
            "UPDATE tables SET status = 'reserved', current_booking_id = ? WHERE id = ?",
            (booking_id, table["id"]),
        )

    return {
        "assigned": True,
        "table_id": table["id"],
        "table_number": table["table_number"],
        "seats": table["seats"],
        "section": table.get("section", ""),
        "location_type": table.get("location_type", ""),
        "booking_id": booking_id,
        "combined": False,
    }


def _assign_combo(db_path: str, booking_id: int, combo: dict[str, Any]) -> dict[str, Any]:
    table_ids = combo["table_ids"]
    with get_db(db_path) as conn:
        primary_id = table_ids[0]
        conn.execute(
            "UPDATE bookings SET table_id = ? WHERE id = ?",
            (primary_id, booking_id),
        )
        for tid in table_ids:
            conn.execute(
                "UPDATE tables SET status = 'reserved', current_booking_id = ? WHERE id = ?",
                (booking_id, tid),
            )

    return {
        "assigned": True,
        "table_id": table_ids[0],
        "table_ids": table_ids,
        "table_numbers": combo["table_numbers"],
        "combined_seats": combo["combined_seats"],
        "booking_id": booking_id,
        "combined": True,
    }


def _parse_preferences(special_requests: str) -> list[str]:
    """Extract location-type preferences from the special requests string."""
    if not special_requests:
        return []
    prefs: list[str] = []
    lower = special_requests.lower()
    for keyword, location_types in PREFERENCE_MAP.items():
        if keyword in lower:
            prefs.extend(location_types)
    return list(set(prefs))


def _score_table(
    table: dict[str, Any],
    party_size: int,
    prefs: list[str],
    section_counts: dict[str, int],
) -> float:
    score = 0.0

    seat_excess = table["seats"] - party_size
    score += max(0, 10 - seat_excess * 2)

    loc = table.get("location_type", "")
    if prefs and loc in prefs:
        score += 20

    section = table.get("section", "main")
    section_load = section_counts.get(section, 0)
    score += max(0, 5 - section_load)

    return score


def _score_combo(
    combo: dict[str, Any],
    party_size: int,
    prefs: list[str],
    section_counts: dict[str, int],
) -> float:
    score = 0.0

    seat_excess = combo["combined_seats"] - party_size
    score += max(0, 8 - seat_excess * 2)

    score -= 3

    return score


def _count_section_bookings(conn: Any, booking_date: str, booking_time: str) -> dict[str, int]:
    """Count active bookings per section for the given date and time."""
    rows = conn.execute(
        """SELECT t.section, COUNT(*) as cnt
           FROM bookings b
           JOIN tables t ON t.id = b.table_id
           WHERE b.booking_date = ?
             AND b.status IN ('pending', 'confirmed')
           GROUP BY t.section""",
        (booking_date,),
    ).fetchall()
    return {r["section"]: r["cnt"] for r in rows}


def _find_combos(
    tables: list[dict[str, Any]],
    party_size: int,
    db_path: str,
    booking_date: str,
    booking_time: str,
    duration: int,
) -> list[dict[str, Any]]:
    """Find combinable table pairs that together seat the party."""
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
