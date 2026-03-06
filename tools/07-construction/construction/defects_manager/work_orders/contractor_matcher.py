"""Auto-match contractors to defects by trade, availability, and performance."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from openclaw_shared.database import get_db

logger = logging.getLogger("openclaw.construction.defects_manager.work_orders.contractor_matcher")

CATEGORY_TO_TRADE: dict[str, str] = {
    "water_seepage": "waterproofing",
    "concrete_spalling": "concrete_repair",
    "plumbing": "plumbing",
    "electrical": "electrical",
    "lift": "lift_maintenance",
    "window": "aluminium_window",
    "common_area": "general_building",
    "structural": "structural_engineering",
    "other": "general_building",
}

SCORING_WEIGHTS = {
    "response_time": 0.40,
    "quality": 0.30,
    "cost": 0.20,
    "communication": 0.10,
}


def _parse_trades(raw: str | None) -> list[str]:
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
        return [t.lower() for t in parsed] if isinstance(parsed, list) else []
    except (json.JSONDecodeError, TypeError):
        return [t.strip().lower() for t in raw.split(",") if t.strip()]


def _score_contractor(contractor: dict) -> float:
    """Compute a weighted score for a contractor (0–100 scale)."""
    response_time = contractor.get("response_time_score", 50)
    quality = contractor.get("quality_score", 50)
    cost = contractor.get("cost_score", 50)
    communication = contractor.get("communication_score", 50)

    return (
        response_time * SCORING_WEIGHTS["response_time"]
        + quality * SCORING_WEIGHTS["quality"]
        + cost * SCORING_WEIGHTS["cost"]
        + communication * SCORING_WEIGHTS["communication"]
    )


def match_contractor(
    db_path: str | Path,
    category: str,
    config: Any = None,
) -> int | None:
    """Find the best-matching active contractor for a defect category.

    Returns the contractor ID or ``None`` if no suitable match exists.
    """
    target_trade = CATEGORY_TO_TRADE.get(category, "general_building")

    with get_db(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM contractors WHERE active = TRUE"
        ).fetchall()

    candidates: list[tuple[int, float]] = []
    for row in rows:
        contractor = dict(row)
        trades = _parse_trades(contractor.get("trades"))

        if target_trade not in trades and "general_building" not in trades:
            continue

        score = _score_contractor(contractor)
        trade_bonus = 10.0 if target_trade in trades else 0.0
        candidates.append((contractor["id"], score + trade_bonus))

    if not candidates:
        logger.info("No matching contractor for category=%s (trade=%s)", category, target_trade)
        return None

    candidates.sort(key=lambda c: c[1], reverse=True)
    best_id, best_score = candidates[0]
    logger.info("Matched contractor #%d (score=%.1f) for %s", best_id, best_score, category)
    return best_id
