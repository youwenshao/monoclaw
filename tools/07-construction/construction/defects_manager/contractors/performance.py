"""Contractor performance scoring based on work order history."""

from __future__ import annotations

import logging
from pathlib import Path

from openclaw_shared.database import get_db

logger = logging.getLogger("openclaw.construction.defects_manager.contractors.performance")

SCORING_WEIGHTS = {
    "response_time": 0.40,
    "quality": 0.30,
    "cost": 0.20,
    "communication": 0.10,
}


def update_performance_score(db_path: str | Path, contractor_id: int) -> float:
    """Recalculate and persist the composite performance score for a contractor.

    Weights: response_time 40%, quality 30%, cost 20%, communication 10%.
    Returns the new composite score (0–100).
    """
    with get_db(db_path) as conn:
        row = conn.execute(
            "SELECT response_time_score, quality_score, cost_score, communication_score "
            "FROM contractors WHERE id = ?",
            (contractor_id,),
        ).fetchone()

        if not row:
            logger.warning("Contractor #%d not found", contractor_id)
            return 0.0

        response_time = row["response_time_score"] or 50
        quality = row["quality_score"] or 50
        cost = row["cost_score"] or 50
        communication = row["communication_score"] or 50

        composite = (
            response_time * SCORING_WEIGHTS["response_time"]
            + quality * SCORING_WEIGHTS["quality"]
            + cost * SCORING_WEIGHTS["cost"]
            + communication * SCORING_WEIGHTS["communication"]
        )

        composite = round(min(max(composite, 0), 100), 1)

        conn.execute(
            "UPDATE contractors SET performance_score = ? WHERE id = ?",
            (composite, contractor_id),
        )

    logger.info("Contractor #%d performance score updated to %.1f", contractor_id, composite)
    return composite


def bulk_update_scores(db_path: str | Path) -> dict[int, float]:
    """Recalculate performance scores for all active contractors.

    Returns a mapping of contractor ID to new score.
    """
    with get_db(db_path) as conn:
        rows = conn.execute(
            "SELECT id FROM contractors WHERE active = TRUE"
        ).fetchall()

    results: dict[int, float] = {}
    for row in rows:
        cid = row["id"]
        results[cid] = update_performance_score(db_path, cid)
    return results
