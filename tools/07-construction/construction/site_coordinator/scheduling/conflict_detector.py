"""Conflict detection for schedule assignments."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from openclaw_shared.database import get_db

from construction.site_coordinator.scheduling.trade_dependencies import validate_assignment

logger = logging.getLogger("openclaw.construction.site_coordinator.conflict_detector")


def check_conflicts(
    db_path: str | Path,
    contractor_id: int,
    site_id: int,
    assignment_date: str,
    trade: str,
) -> list[dict[str, Any]]:
    """Return a list of conflict dicts for the proposed assignment.

    Checks:
    1. Double-booking — contractor already assigned elsewhere that day.
    2. Site capacity overflow — site exceeds max_daily_workers.
    3. Trade dependency violations — prerequisite trades not completed.
    """
    conflicts: list[dict[str, Any]] = []

    with get_db(db_path) as conn:
        # 1. Double-booking
        existing = conn.execute(
            "SELECT sa.id, sa.site_id, s.site_name, sa.start_time, sa.end_time "
            "FROM schedule_assignments sa "
            "LEFT JOIN sites s ON sa.site_id = s.id "
            "WHERE sa.contractor_id = ? AND sa.assignment_date = ? "
            "AND sa.status NOT IN ('cancelled', 'rescheduled')",
            (contractor_id, assignment_date),
        ).fetchall()

        for row in existing:
            if row["site_id"] != site_id:
                conflicts.append({
                    "type": "double_booking",
                    "severity": "error",
                    "message": (
                        f"Contractor already assigned to {row['site_name'] or 'site ' + str(row['site_id'])} "
                        f"on {assignment_date} ({row['start_time']}–{row['end_time']})"
                    ),
                    "existing_assignment_id": row["id"],
                })

        # 2. Site capacity overflow
        site_row = conn.execute(
            "SELECT max_daily_workers FROM sites WHERE id = ?", (site_id,)
        ).fetchone()
        max_workers = site_row["max_daily_workers"] if site_row else 0

        if max_workers > 0:
            worker_count = conn.execute(
                "SELECT COUNT(DISTINCT contractor_id) AS cnt "
                "FROM schedule_assignments "
                "WHERE site_id = ? AND assignment_date = ? "
                "AND status NOT IN ('cancelled', 'rescheduled')",
                (site_id, assignment_date),
            ).fetchone()

            current = worker_count["cnt"] if worker_count else 0
            if current >= max_workers:
                conflicts.append({
                    "type": "capacity_overflow",
                    "severity": "warning",
                    "message": (
                        f"Site already at capacity ({current}/{max_workers} contractors) "
                        f"on {assignment_date}"
                    ),
                    "current_count": current,
                    "max_workers": max_workers,
                })

    # 3. Trade dependency violations
    if trade:
        violations = validate_assignment(db_path, site_id, trade, assignment_date)
        for msg in violations:
            conflicts.append({
                "type": "trade_dependency",
                "severity": "warning",
                "message": msg,
            })

    if conflicts:
        logger.info(
            "Found %d conflicts for contractor %d at site %d on %s",
            len(conflicts), contractor_id, site_id, assignment_date,
        )
    return conflicts
