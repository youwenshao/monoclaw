"""PRISMA-style systematic review workflow management."""

from __future__ import annotations

import logging
from typing import Any

from openclaw_shared.database import get_db

logger = logging.getLogger("openclaw.academic.paper_sieve.systematic_review")

_VALID_STATUSES = {"screening", "data_extraction", "synthesis", "completed", "archived"}


def create_review(
    db_path: str,
    review_name: str,
    research_question: str,
    inclusion_criteria: str,
    exclusion_criteria: str,
) -> int:
    """Create a new systematic review and return its id."""
    with get_db(db_path) as conn:
        cursor = conn.execute(
            "INSERT INTO systematic_reviews "
            "(review_name, research_question, inclusion_criteria, exclusion_criteria) "
            "VALUES (?, ?, ?, ?)",
            (review_name, research_question, inclusion_criteria, exclusion_criteria),
        )
        review_id: int = cursor.lastrowid  # type: ignore[assignment]

    logger.info("Created systematic review id=%d: %s", review_id, review_name)
    return review_id


def get_review(db_path: str, review_id: int) -> dict[str, Any] | None:
    """Fetch a single systematic review by id, or None if not found."""
    with get_db(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM systematic_reviews WHERE id = ?", (review_id,)
        ).fetchone()
    return dict(row) if row else None


def get_reviews(db_path: str) -> list[dict[str, Any]]:
    """Return all systematic reviews ordered by creation date descending."""
    with get_db(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM systematic_reviews ORDER BY created_at DESC"
        ).fetchall()
    return [dict(r) for r in rows]


def update_review_status(db_path: str, review_id: int, status: str) -> bool:
    """Advance the review to a new workflow *status*.

    Returns True if the update succeeded, False if the review was not found
    or the status value is invalid.
    """
    if status not in _VALID_STATUSES:
        logger.warning("Invalid review status: %s", status)
        return False

    with get_db(db_path) as conn:
        cursor = conn.execute(
            "UPDATE systematic_reviews SET status = ? WHERE id = ?",
            (status, review_id),
        )
        updated = cursor.rowcount > 0

    if updated:
        logger.info("Review id=%d status -> %s", review_id, status)
    return updated


def add_papers_to_review(
    db_path: str,
    review_id: int,
    paper_ids: list[int],
) -> int:
    """Add papers for screening in the review. Returns the number added."""
    if not paper_ids:
        return 0

    added = 0
    with get_db(db_path) as conn:
        for pid in paper_ids:
            existing = conn.execute(
                "SELECT id FROM review_papers WHERE review_id = ? AND paper_id = ?",
                (review_id, pid),
            ).fetchone()
            if existing:
                continue
            conn.execute(
                "INSERT INTO review_papers (review_id, paper_id, screening_status) "
                "VALUES (?, ?, 'pending')",
                (review_id, pid),
            )
            added += 1

    logger.info("Added %d papers to review id=%d", added, review_id)
    return added


def get_review_stats(db_path: str, review_id: int) -> dict[str, Any]:
    """Return screening-status counts for the review."""
    with get_db(db_path) as conn:
        rows = conn.execute(
            "SELECT screening_status, COUNT(*) AS cnt "
            "FROM review_papers WHERE review_id = ? "
            "GROUP BY screening_status",
            (review_id,),
        ).fetchall()

    stats: dict[str, int] = {s: 0 for s in ("pending", "included", "excluded", "maybe")}
    total = 0
    for row in rows:
        stats[row["screening_status"]] = row["cnt"]
        total += row["cnt"]

    return {"review_id": review_id, "total": total, **stats}
