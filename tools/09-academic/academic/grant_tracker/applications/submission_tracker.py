"""Application lifecycle tracking – create, update, and query grant applications."""

from __future__ import annotations

import logging
from datetime import date
from pathlib import Path
from typing import Any

from openclaw_shared.database import get_db

logger = logging.getLogger("openclaw.academic.grant_tracker.applications.tracker")

VALID_TRANSITIONS: dict[str, list[str]] = {
    "planning": ["drafting", "withdrawn"],
    "drafting": ["internal_review", "withdrawn"],
    "internal_review": ["drafting", "submitted", "withdrawn"],
    "submitted": ["under_review", "withdrawn"],
    "under_review": ["awarded", "rejected"],
    "awarded": [],
    "rejected": [],
    "withdrawn": [],
}


def create_application(
    db_path: str | Path,
    researcher_id: int,
    scheme_id: int,
    deadline_id: int,
    project_title: str,
    **kwargs: Any,
) -> int:
    """Insert a new grant application and return its ID.

    Keyword args can include: requested_amount, duration_months, notes.
    """
    with get_db(db_path) as conn:
        cur = conn.execute(
            """INSERT INTO applications
               (researcher_id, scheme_id, deadline_id, project_title,
                requested_amount, duration_months, status, notes)
               VALUES (?, ?, ?, ?, ?, ?, 'planning', ?)""",
            (
                researcher_id,
                scheme_id,
                deadline_id,
                project_title,
                kwargs.get("requested_amount"),
                kwargs.get("duration_months"),
                kwargs.get("notes", ""),
            ),
        )
        app_id: int = cur.lastrowid  # type: ignore[assignment]

    logger.info("Created application %d: '%s'", app_id, project_title)
    return app_id


def update_application_status(
    db_path: str | Path,
    application_id: int,
    new_status: str,
    **kwargs: Any,
) -> bool:
    """Transition an application to a new status with validation.

    Returns True on success, False if the transition is invalid.

    Keyword args can include: submission_date, outcome_date,
    awarded_amount, reviewer_score, reviewer_comments, notes.
    """
    with get_db(db_path) as conn:
        row = conn.execute(
            "SELECT status FROM applications WHERE id = ?",
            (application_id,),
        ).fetchone()
        if not row:
            logger.warning("Application %d not found", application_id)
            return False

        current = row["status"]
        allowed = VALID_TRANSITIONS.get(current, [])
        if new_status not in allowed:
            logger.warning(
                "Invalid transition for application %d: %s → %s (allowed: %s)",
                application_id, current, new_status, allowed,
            )
            return False

        set_clauses = ["status = ?"]
        params: list[Any] = [new_status]

        if new_status == "submitted":
            set_clauses.append("submission_date = ?")
            params.append(kwargs.get("submission_date", date.today().isoformat()))

        if new_status in ("awarded", "rejected"):
            set_clauses.append("outcome_date = ?")
            params.append(kwargs.get("outcome_date", date.today().isoformat()))

        for field in ("awarded_amount", "reviewer_score", "reviewer_comments", "notes"):
            if field in kwargs:
                set_clauses.append(f"{field} = ?")
                params.append(kwargs[field])

        params.append(application_id)
        conn.execute(
            f"UPDATE applications SET {', '.join(set_clauses)} WHERE id = ?",
            params,
        )

    logger.info("Application %d: %s → %s", application_id, current, new_status)
    return True


def get_applications(
    db_path: str | Path,
    researcher_id: int | None = None,
    status: str | None = None,
) -> list[dict]:
    """Return applications with optional filters.

    Joins grant_schemes and deadlines for richer data.
    """
    query = """
        SELECT a.*, gs.scheme_name, gs.scheme_code, gs.agency,
               d.external_deadline, d.institutional_deadline
        FROM applications a
        JOIN grant_schemes gs ON gs.id = a.scheme_id
        LEFT JOIN deadlines d ON d.id = a.deadline_id
        WHERE 1=1
    """
    params: list[Any] = []

    if researcher_id is not None:
        query += " AND a.researcher_id = ?"
        params.append(researcher_id)

    if status is not None:
        query += " AND a.status = ?"
        params.append(status)

    query += " ORDER BY a.created_at DESC"

    with get_db(db_path) as conn:
        rows = conn.execute(query, params).fetchall()

    return [dict(r) for r in rows]


def get_application_detail(db_path: str | Path, application_id: int) -> dict | None:
    """Return full details for a single application, including budget summary."""
    with get_db(db_path) as conn:
        row = conn.execute(
            """SELECT a.*, gs.scheme_name, gs.scheme_code, gs.agency, gs.url AS scheme_url,
                      d.external_deadline, d.institutional_deadline, d.call_url,
                      r.name_en AS pi_name, r.department, r.institution
               FROM applications a
               JOIN grant_schemes gs ON gs.id = a.scheme_id
               LEFT JOIN deadlines d ON d.id = a.deadline_id
               LEFT JOIN researchers r ON r.id = a.researcher_id
               WHERE a.id = ?""",
            (application_id,),
        ).fetchone()

        if not row:
            return None

        detail = dict(row)

        budget_rows = conn.execute(
            "SELECT * FROM budget_items WHERE application_id = ? ORDER BY year, category",
            (application_id,),
        ).fetchall()
        detail["budget_items"] = [dict(b) for b in budget_rows]
        detail["budget_total"] = sum(
            (b.get("amount", 0) or 0) for b in detail["budget_items"]
        )

    return detail
