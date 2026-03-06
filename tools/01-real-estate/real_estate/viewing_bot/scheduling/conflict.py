"""Conflict detection for proposed viewing times."""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from openclaw_shared.database import get_db

VIEWING_DURATION_MINUTES = 30

DISTRICT_TRAVEL_MATRIX: dict[tuple[str, str], int] = {
    ("Central & Western", "Wan Chai"): 10,
    ("Wan Chai", "Eastern"): 15,
    ("Eastern", "Southern"): 20,
    ("Yau Tsim Mong", "Sham Shui Po"): 10,
    ("Sham Shui Po", "Kowloon City"): 10,
    ("Kowloon City", "Wong Tai Sin"): 10,
    ("Wong Tai Sin", "Kwun Tong"): 10,
    ("Yau Tsim Mong", "Kowloon City"): 12,
    ("Sha Tin", "Tai Po"): 15,
    ("Tai Po", "North"): 20,
    ("Tuen Mun", "Yuen Long"): 15,
    ("Yuen Long", "Tai Po"): 25,
    ("Tsuen Wan", "Kwai Tsing"): 10,
    ("Kwai Tsing", "Sham Shui Po"): 15,
    ("Islands", "Tsuen Wan"): 30,
    ("Sai Kung", "Sha Tin"): 20,
    ("Sai Kung", "Kwun Tong"): 20,
}

HK_CROSS_HARBOUR_PENALTY = 20
NT_PENALTY = 30

HK_ISLAND_DISTRICTS = {"Central & Western", "Wan Chai", "Eastern", "Southern"}
KOWLOON_DISTRICTS = {"Yau Tsim Mong", "Sham Shui Po", "Kowloon City", "Wong Tai Sin", "Kwun Tong"}
NT_DISTRICTS = {"Sha Tin", "Tai Po", "North", "Tuen Mun", "Yuen Long", "Tsuen Wan", "Kwai Tsing", "Islands", "Sai Kung"}


def _get_travel_minutes(from_district: str, to_district: str) -> int:
    """Estimate travel minutes between two HK districts."""
    if from_district == to_district:
        return 5

    pair = (from_district, to_district)
    reverse = (to_district, from_district)
    if pair in DISTRICT_TRAVEL_MATRIX:
        return DISTRICT_TRAVEL_MATRIX[pair]
    if reverse in DISTRICT_TRAVEL_MATRIX:
        return DISTRICT_TRAVEL_MATRIX[reverse]

    from_region = (
        "hk" if from_district in HK_ISLAND_DISTRICTS
        else "kl" if from_district in KOWLOON_DISTRICTS
        else "nt"
    )
    to_region = (
        "hk" if to_district in HK_ISLAND_DISTRICTS
        else "kl" if to_district in KOWLOON_DISTRICTS
        else "nt"
    )

    if from_region == to_region:
        return 15
    if {from_region, to_region} == {"hk", "kl"}:
        return HK_CROSS_HARBOUR_PENALTY
    if "nt" in {from_region, to_region}:
        return NT_PENALTY
    return 25


def detect_conflicts(
    db_path: str | Path,
    proposed_datetime: datetime,
    agent_phone: str,
    district: str,
) -> list[dict[str, Any]]:
    """Check for scheduling conflicts with existing viewings.

    Returns a list of conflict dicts, each with: viewing_id, type, detail, severity.
    An empty list means no conflicts detected.
    """
    window_start = proposed_datetime - timedelta(hours=2)
    window_end = proposed_datetime + timedelta(hours=2)

    with get_db(db_path) as conn:
        nearby = conn.execute(
            """SELECT id, property_ref, property_address, district,
                      proposed_datetime, confirmed_datetime, status
               FROM viewings
               WHERE agent_phone = ?
                 AND status NOT IN ('cancelled')
                 AND COALESCE(confirmed_datetime, proposed_datetime) BETWEEN ? AND ?""",
            (agent_phone, window_start.isoformat(), window_end.isoformat()),
        ).fetchall()

    conflicts: list[dict[str, Any]] = []

    for row in nearby:
        viewing = dict(row)
        existing_dt_str = viewing["confirmed_datetime"] or viewing["proposed_datetime"]
        try:
            existing_dt = datetime.fromisoformat(existing_dt_str)
        except (ValueError, TypeError):
            continue

        gap_minutes = abs((proposed_datetime - existing_dt).total_seconds()) / 60

        if gap_minutes < VIEWING_DURATION_MINUTES:
            conflicts.append({
                "viewing_id": viewing["id"],
                "type": "double_booking",
                "detail": (
                    f"Overlaps with viewing #{viewing['id']} at {viewing['property_ref']} "
                    f"({existing_dt.strftime('%H:%M')})"
                ),
                "severity": "error",
            })
            continue

        existing_district = viewing.get("district") or ""
        if existing_district and district:
            travel = _get_travel_minutes(existing_district, district)
            if gap_minutes < travel + VIEWING_DURATION_MINUTES:
                conflicts.append({
                    "viewing_id": viewing["id"],
                    "type": "travel_time",
                    "detail": (
                        f"Only {int(gap_minutes)}min gap to viewing #{viewing['id']} "
                        f"in {existing_district}, but travel takes ~{travel}min + "
                        f"{VIEWING_DURATION_MINUTES}min viewing"
                    ),
                    "severity": "warning",
                })

    return conflicts
