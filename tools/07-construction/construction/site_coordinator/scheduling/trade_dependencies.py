"""Trade sequencing DAG for HK construction projects."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from openclaw_shared.database import get_db

logger = logging.getLogger("openclaw.construction.site_coordinator.trade_dependencies")

TRADE_ORDER: list[str] = [
    "demolition",
    "excavation",
    "piling",
    "formwork",
    "rebar",
    "concreting",
    "structural_steel",
    "plumbing",
    "electrical",
    "hvac",
    "fire_services",
    "plastering",
    "waterproofing",
    "tiling",
    "carpentry",
    "glazing",
    "painting",
    "landscaping",
]

TRADE_DEPENDENCIES: dict[str, list[str]] = {
    "demolition": [],
    "excavation": ["demolition"],
    "piling": ["excavation"],
    "formwork": ["piling"],
    "rebar": ["formwork"],
    "concreting": ["rebar"],
    "structural_steel": ["concreting"],
    "plumbing": ["concreting"],
    "electrical": ["concreting"],
    "hvac": ["concreting"],
    "fire_services": ["concreting"],
    "plastering": ["plumbing", "electrical", "hvac", "fire_services"],
    "waterproofing": ["plastering"],
    "tiling": ["waterproofing"],
    "carpentry": ["plastering"],
    "glazing": ["structural_steel"],
    "painting": ["plastering", "carpentry"],
    "landscaping": ["painting", "tiling", "glazing"],
}


def get_trade_order() -> list[str]:
    """Return the canonical HK construction trade sequence."""
    return list(TRADE_ORDER)


def load_trade_dependencies(db_path: str | Path) -> list[dict[str, Any]]:
    """Load trade dependency overrides from the database.

    Falls back to the built-in DAG when no rows exist.
    """
    with get_db(db_path) as conn:
        rows = conn.execute(
            "SELECT trade, depends_on, min_gap_days FROM trade_dependencies"
        ).fetchall()

    if rows:
        logger.debug("Loaded %d trade dependency rows from DB", len(rows))
        return [dict(r) for r in rows]

    result: list[dict[str, Any]] = []
    for trade, deps in TRADE_DEPENDENCIES.items():
        for dep in deps:
            result.append({"trade": trade, "depends_on": dep, "min_gap_days": 1})
    return result


def validate_assignment(
    db_path: str | Path,
    site_id: int,
    trade: str,
    assignment_date: str,
) -> list[str]:
    """Check whether scheduling *trade* at *site_id* on *assignment_date* violates
    any dependency constraints.  Returns a list of human-readable violation strings
    (empty list means OK).
    """
    trade_lower = trade.lower().strip()
    required = TRADE_DEPENDENCIES.get(trade_lower, [])
    if not required:
        return []

    violations: list[str] = []
    with get_db(db_path) as conn:
        for dep_trade in required:
            row = conn.execute(
                "SELECT COUNT(*) AS cnt FROM schedule_assignments "
                "WHERE site_id = ? AND LOWER(trade) = ? AND status = 'completed' "
                "AND assignment_date < ?",
                (site_id, dep_trade, assignment_date),
            ).fetchone()

            if row["cnt"] == 0:
                violations.append(
                    f"Trade '{trade}' requires '{dep_trade}' to be completed first at site {site_id}"
                )

    if violations:
        logger.info(
            "Trade dependency violations for %s at site %d on %s: %s",
            trade, site_id, assignment_date, violations,
        )
    return violations
