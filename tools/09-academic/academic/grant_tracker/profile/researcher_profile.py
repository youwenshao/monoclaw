"""PI (Principal Investigator) profile CRUD operations."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from openclaw_shared.database import get_db

logger = logging.getLogger("openclaw.academic.grant_tracker.profile.researcher")


def create_researcher(
    db_path: str | Path,
    name_en: str,
    name_tc: str = "",
    **kwargs: Any,
) -> int:
    """Create a new researcher profile and return its ID.

    Keyword args can include: title, department, institution, email,
    orcid, google_scholar_id, research_interests, appointment_date.
    """
    with get_db(db_path) as conn:
        cur = conn.execute(
            """INSERT INTO researchers
               (name_en, name_tc, title, department, institution, email,
                orcid, google_scholar_id, research_interests, appointment_date)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                name_en,
                name_tc,
                kwargs.get("title", ""),
                kwargs.get("department", ""),
                kwargs.get("institution", ""),
                kwargs.get("email", ""),
                kwargs.get("orcid", ""),
                kwargs.get("google_scholar_id", ""),
                kwargs.get("research_interests", ""),
                kwargs.get("appointment_date"),
            ),
        )
        rid: int = cur.lastrowid  # type: ignore[assignment]

    logger.info("Created researcher %d: %s", rid, name_en)
    return rid


def get_researcher(db_path: str | Path, researcher_id: int) -> dict | None:
    """Fetch a single researcher profile by ID."""
    with get_db(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM researchers WHERE id = ?", (researcher_id,)
        ).fetchone()
    return dict(row) if row else None


def update_researcher(
    db_path: str | Path,
    researcher_id: int,
    **fields: Any,
) -> bool:
    """Update researcher fields. Returns True on success.

    Accepted fields: name_en, name_tc, title, department, institution,
    email, orcid, google_scholar_id, research_interests, appointment_date.
    """
    allowed = {
        "name_en", "name_tc", "title", "department", "institution",
        "email", "orcid", "google_scholar_id", "research_interests",
        "appointment_date",
    }
    updates = {k: v for k, v in fields.items() if k in allowed}
    if not updates:
        return False

    set_clause = ", ".join(f"{k} = ?" for k in updates)
    params = list(updates.values()) + [researcher_id]

    with get_db(db_path) as conn:
        cur = conn.execute(
            f"UPDATE researchers SET {set_clause} WHERE id = ?",
            params,
        )

    updated = cur.rowcount > 0
    if updated:
        logger.info("Updated researcher %d: %s", researcher_id, list(updates.keys()))
    return updated


def get_primary_researcher(db_path: str | Path) -> dict | None:
    """Return the first / default researcher profile.

    This is the single-user convenience accessor: in a solo-academic
    setup there is typically one researcher row.
    """
    with get_db(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM researchers ORDER BY id ASC LIMIT 1"
        ).fetchone()
    return dict(row) if row else None
