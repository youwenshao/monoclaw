"""Inclusion/exclusion screening for systematic reviews."""

from __future__ import annotations

import json
import logging
from typing import Any

from openclaw_shared.database import get_db

logger = logging.getLogger("openclaw.academic.paper_sieve.screening")

_VALID_SCREENING = {"included", "excluded", "maybe"}


def screen_paper(
    db_path: str,
    review_id: int,
    paper_id: int,
    status: str,
    reason: str = "",
) -> bool:
    """Set the screening status of a paper within a review.

    *status* must be one of 'included', 'excluded', or 'maybe'.
    Returns True on success, False if the review-paper row was not found.
    """
    if status not in _VALID_SCREENING:
        logger.warning("Invalid screening status: %s", status)
        return False

    with get_db(db_path) as conn:
        cursor = conn.execute(
            "UPDATE review_papers SET screening_status = ?, exclusion_reason = ? "
            "WHERE review_id = ? AND paper_id = ?",
            (status, reason, review_id, paper_id),
        )
        updated = cursor.rowcount > 0

    if updated:
        logger.info(
            "Paper %d in review %d screened as %s", paper_id, review_id, status,
        )
    return updated


def get_papers_for_screening(
    db_path: str,
    review_id: int,
    status: str = "pending",
) -> list[dict[str, Any]]:
    """Fetch papers to screen, joined with paper metadata from the papers table."""
    with get_db(db_path) as conn:
        rows = conn.execute(
            "SELECT rp.id AS review_paper_id, rp.paper_id, rp.screening_status, "
            "       rp.exclusion_reason, rp.quality_score, "
            "       p.title, p.authors, p.abstract, p.year, p.journal, p.doi "
            "FROM review_papers rp "
            "JOIN papers p ON p.id = rp.paper_id "
            "WHERE rp.review_id = ? AND rp.screening_status = ? "
            "ORDER BY p.year DESC",
            (review_id, status),
        ).fetchall()
    return [dict(r) for r in rows]


def auto_screen(
    db_path: str,
    review_id: int,
    llm: Any,
) -> list[dict[str, Any]]:
    """LLM-assisted screening of pending papers against inclusion/exclusion criteria.

    For each pending paper the LLM receives the title, abstract, and review
    criteria, then returns a decision (included / excluded / maybe) with a
    short justification.  Decisions are persisted automatically.

    Returns a list of {paper_id, title, decision, reason} dicts.
    """
    with get_db(db_path) as conn:
        review = conn.execute(
            "SELECT inclusion_criteria, exclusion_criteria FROM systematic_reviews WHERE id = ?",
            (review_id,),
        ).fetchone()

    if not review:
        logger.warning("Review id=%d not found", review_id)
        return []

    inclusion = review["inclusion_criteria"]
    exclusion = review["exclusion_criteria"]

    pending = get_papers_for_screening(db_path, review_id, status="pending")
    if not pending:
        return []

    decisions: list[dict[str, Any]] = []
    for paper in pending:
        prompt = (
            "You are screening papers for a systematic review.\n\n"
            f"Inclusion criteria: {inclusion}\n"
            f"Exclusion criteria: {exclusion}\n\n"
            f"Paper title: {paper['title']}\n"
            f"Authors: {paper['authors']}\n"
            f"Year: {paper['year']}\n"
            f"Abstract: {paper.get('abstract', 'N/A')}\n\n"
            "Respond with EXACTLY one JSON object on a single line:\n"
            '{"decision": "included|excluded|maybe", "reason": "brief justification"}'
        )

        raw = llm.generate(prompt).strip()
        try:
            parsed = json.loads(raw)
            decision = parsed.get("decision", "maybe")
            reason = parsed.get("reason", "")
        except (json.JSONDecodeError, AttributeError):
            decision = "maybe"
            reason = f"LLM parse error – raw: {raw[:200]}"

        if decision not in _VALID_SCREENING:
            decision = "maybe"

        screen_paper(db_path, review_id, paper["paper_id"], decision, reason)
        decisions.append({
            "paper_id": paper["paper_id"],
            "title": paper["title"],
            "decision": decision,
            "reason": reason,
        })

    logger.info("Auto-screened %d papers for review id=%d", len(decisions), review_id)
    return decisions
