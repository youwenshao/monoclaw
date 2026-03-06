"""Calendar management with HK public holidays and typhoon rescheduling."""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from openclaw_shared.database import get_db

logger = logging.getLogger("openclaw.construction.site_coordinator.calendar_manager")

# HK public holidays (month, day) — fixed-date holidays only.
# Lunar / variable-date holidays would need yearly config.
HK_FIXED_HOLIDAYS: list[tuple[int, int]] = [
    (1, 1),   # New Year's Day
    (5, 1),   # Labour Day
    (7, 1),   # HKSAR Establishment Day
    (10, 1),  # National Day
    (12, 25), # Christmas Day
    (12, 26), # Boxing Day
]

OUTDOOR_TRADES: set[str] = {
    "demolition", "excavation", "piling", "concreting",
    "formwork", "rebar", "structural_steel", "landscaping",
    "waterproofing", "glazing",
}


def is_hk_holiday(check_date: date) -> bool:
    """Check whether *check_date* falls on a known HK fixed public holiday."""
    return (check_date.month, check_date.day) in HK_FIXED_HOLIDAYS


def next_working_day(from_date: date) -> date:
    """Return the next non-weekend, non-holiday date after *from_date*."""
    candidate = from_date + timedelta(days=1)
    while candidate.weekday() >= 5 or is_hk_holiday(candidate):
        candidate += timedelta(days=1)
    return candidate


def get_weekly_schedule(
    db_path: str | Path,
    week_start: str,
) -> dict[str, Any]:
    """Build a contractor × day matrix for the given week.

    Returns::

        {
            "week_start": "2026-03-02",
            "week_end": "2026-03-08",
            "contractors": { <contractor_id>: { "name": ..., "days": { "Mon": [...], ... } } },
            "unassigned_days": ["2026-03-04"],
        }
    """
    ws = date.fromisoformat(week_start)
    we = ws + timedelta(days=6)
    day_labels = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

    with get_db(db_path) as conn:
        rows = conn.execute(
            "SELECT sa.*, c.company_name, s.site_name "
            "FROM schedule_assignments sa "
            "LEFT JOIN contractors c ON sa.contractor_id = c.id "
            "LEFT JOIN sites s ON sa.site_id = s.id "
            "WHERE sa.assignment_date BETWEEN ? AND ? "
            "AND sa.status NOT IN ('cancelled', 'rescheduled') "
            "ORDER BY sa.contractor_id, sa.assignment_date",
            (ws.isoformat(), we.isoformat()),
        ).fetchall()

    contractors: dict[int, dict[str, Any]] = {}
    unassigned_days: list[str] = []

    date_to_label = {}
    for i in range(7):
        d = ws + timedelta(days=i)
        date_to_label[d.isoformat()] = day_labels[i]

    for row in rows:
        r = dict(row)
        c_id = r["contractor_id"]
        if c_id not in contractors:
            contractors[c_id] = {
                "name": r.get("company_name", f"Contractor {c_id}"),
                "days": {label: [] for label in day_labels},
            }
        label = date_to_label.get(str(r["assignment_date"])[:10], "")
        if label:
            contractors[c_id]["days"][label].append({
                "assignment_id": r["id"],
                "site_name": r.get("site_name", ""),
                "site_id": r.get("site_id"),
                "trade": r.get("trade", ""),
                "start_time": r.get("start_time", ""),
                "end_time": r.get("end_time", ""),
                "status": r.get("status", ""),
            })

    assigned_dates = set()
    for row in rows:
        assigned_dates.add(str(dict(row)["assignment_date"])[:10])
    for i in range(7):
        d = (ws + timedelta(days=i))
        ds = d.isoformat()
        if ds not in assigned_dates and d.weekday() < 5 and not is_hk_holiday(d):
            unassigned_days.append(ds)

    return {
        "week_start": ws.isoformat(),
        "week_end": we.isoformat(),
        "contractors": contractors,
        "unassigned_days": unassigned_days,
    }


def reschedule_for_typhoon(
    db_path: str | Path,
    date_str: str,
) -> dict[str, Any]:
    """Reschedule all outdoor assignments on *date_str* to the next working day.

    Returns summary with counts and the new target date.
    """
    typhoon_date = date.fromisoformat(date_str)
    new_date = next_working_day(typhoon_date)
    rescheduled = 0
    kept = 0

    outdoor_filter = ", ".join(f"'{t}'" for t in OUTDOOR_TRADES)

    with get_db(db_path) as conn:
        outdoor_rows = conn.execute(
            f"SELECT id, trade FROM schedule_assignments "
            f"WHERE assignment_date = ? "
            f"AND status NOT IN ('cancelled', 'completed', 'rescheduled') "
            f"AND LOWER(trade) IN ({outdoor_filter})",
            (date_str,),
        ).fetchall()

        for row in outdoor_rows:
            conn.execute(
                "UPDATE schedule_assignments SET status = 'rescheduled' WHERE id = ?",
                (row["id"],),
            )
            conn.execute(
                "INSERT INTO schedule_assignments "
                "(site_id, contractor_id, assignment_date, start_time, end_time, "
                "trade, status, priority, scope_of_work) "
                "SELECT site_id, contractor_id, ?, start_time, end_time, "
                "trade, 'scheduled', priority, scope_of_work "
                "FROM schedule_assignments WHERE id = ?",
                (new_date.isoformat(), row["id"]),
            )
            rescheduled += 1

        indoor_count = conn.execute(
            "SELECT COUNT(*) AS cnt FROM schedule_assignments "
            "WHERE assignment_date = ? "
            "AND status NOT IN ('cancelled', 'completed', 'rescheduled')",
            (date_str,),
        ).fetchone()
        kept = indoor_count["cnt"] if indoor_count else 0

    logger.warning(
        "Typhoon reschedule on %s: %d outdoor assignments moved to %s, %d indoor kept",
        date_str, rescheduled, new_date.isoformat(), kept,
    )

    return {
        "rescheduled": rescheduled,
        "kept_indoor": kept,
        "original_date": date_str,
        "new_date": new_date.isoformat(),
    }
