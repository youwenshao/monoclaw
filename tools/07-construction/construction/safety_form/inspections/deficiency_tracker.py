"""Deficiency lifecycle tracking — open, resolve, close."""

from __future__ import annotations

import logging
from datetime import date
from pathlib import Path
from typing import Any

from openclaw_shared.database import get_db

logger = logging.getLogger("openclaw.construction.safety_form.inspections.deficiency")


def update_deficiency_status(
    db_path: str | Path,
    deficiency_id: int,
    new_status: str,
    resolved_by: str = "",
) -> None:
    """Transition a deficiency to a new status.

    Valid statuses: open, in_progress, resolved, closed.
    Setting 'resolved' or 'closed' records the resolved_date and resolved_by.
    """
    valid_statuses = {"open", "in_progress", "resolved", "closed"}
    if new_status not in valid_statuses:
        raise ValueError(f"Invalid status '{new_status}'; expected one of {valid_statuses}")

    with get_db(db_path) as conn:
        existing = conn.execute(
            "SELECT id, status FROM deficiencies WHERE id = ?", (deficiency_id,)
        ).fetchone()
        if not existing:
            raise ValueError(f"Deficiency #{deficiency_id} not found")

        if new_status in ("resolved", "closed"):
            conn.execute(
                "UPDATE deficiencies SET status = ?, resolved_date = ?, resolved_by = ? WHERE id = ?",
                (new_status, date.today().isoformat(), resolved_by, deficiency_id),
            )
        else:
            conn.execute(
                "UPDATE deficiencies SET status = ? WHERE id = ?",
                (new_status, deficiency_id),
            )

    logger.info(
        "Deficiency #%d: %s -> %s (by %s)",
        deficiency_id, existing["status"], new_status, resolved_by or "system",
    )


def get_open_deficiencies(
    db_path: str | Path,
    site_id: int | None = None,
) -> list[dict]:
    """Retrieve all open/in-progress deficiencies, optionally filtered by site."""
    query = (
        "SELECT d.*, s.site_name FROM deficiencies d "
        "LEFT JOIN sites s ON d.site_id = s.id "
        "WHERE d.status IN ('open', 'in_progress')"
    )
    params: list[Any] = []

    if site_id is not None:
        query += " AND d.site_id = ?"
        params.append(site_id)

    query += " ORDER BY CASE d.severity "
    query += "WHEN 'critical' THEN 1 WHEN 'major' THEN 2 WHEN 'minor' THEN 3 ELSE 4 END, "
    query += "d.reported_date ASC"

    with get_db(db_path) as conn:
        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]


def get_deficiency_summary(db_path: str | Path, site_id: int | None = None) -> dict:
    """Return a summary of deficiency counts by severity and status."""
    base_where = ""
    params: list[Any] = []
    if site_id is not None:
        base_where = "WHERE site_id = ?"
        params = [site_id]

    with get_db(db_path) as conn:
        by_severity = {}
        for row in conn.execute(
            f"SELECT severity, COUNT(*) as cnt FROM deficiencies {base_where} GROUP BY severity",
            params,
        ).fetchall():
            by_severity[row["severity"]] = row["cnt"]

        by_status = {}
        for row in conn.execute(
            f"SELECT status, COUNT(*) as cnt FROM deficiencies {base_where} GROUP BY status",
            params,
        ).fetchall():
            by_status[row["status"]] = row["cnt"]

        overdue = conn.execute(
            f"SELECT COUNT(*) FROM deficiencies {base_where}"
            + (" AND " if base_where else " WHERE ")
            + "due_date < ? AND status IN ('open','in_progress')",
            params + [date.today().isoformat()],
        ).fetchone()[0]

    return {
        "by_severity": by_severity,
        "by_status": by_status,
        "overdue": overdue,
    }
