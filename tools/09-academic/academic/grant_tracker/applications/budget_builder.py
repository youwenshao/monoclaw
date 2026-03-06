"""Budget template handling – create, summarise, and validate grant budgets."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from openclaw_shared.database import get_db

logger = logging.getLogger("openclaw.academic.grant_tracker.applications.budget")

RGC_BUDGET_CATEGORIES: list[str] = [
    "ra_salary",
    "postdoc_salary",
    "equipment",
    "travel",
    "consumables",
    "services",
    "other",
]

DEFAULT_SALARY_NORMS: dict[str, dict[str, Any]] = {
    "ra": {
        "monthly_low": 18_000,
        "monthly_high": 23_000,
        "currency": "HKD",
        "notes": "Research Assistant – typical HK norms",
    },
    "postdoc": {
        "monthly_low": 28_000,
        "monthly_high": 38_000,
        "currency": "HKD",
        "notes": "Post-doctoral Fellow – typical HK norms",
    },
    "senior_ra": {
        "monthly_low": 23_000,
        "monthly_high": 30_000,
        "currency": "HKD",
        "notes": "Senior Research Assistant – typical HK norms",
    },
}

_SCHEME_LIMITS: dict[str, dict[str, Any]] = {
    "GRF": {
        "max_total": 1_500_000,
        "max_equipment_pct": 0.30,
        "max_travel_pct": 0.15,
        "max_duration_years": 3,
        "notes": "GRF funding ceiling ~HK$1.5M (project dependent)",
    },
    "ECS": {
        "max_total": 1_300_000,
        "max_equipment_pct": 0.25,
        "max_travel_pct": 0.15,
        "max_duration_years": 3,
        "notes": "ECS max HK$1.3M including on-costs",
    },
    "CRF": {
        "max_total": 8_000_000,
        "max_equipment_pct": 0.40,
        "max_travel_pct": 0.10,
        "max_duration_years": 5,
        "notes": "CRF ceiling varies; group projects can request more",
    },
    "ITF": {
        "max_total": 10_000_000,
        "max_equipment_pct": 0.40,
        "max_travel_pct": 0.10,
        "max_duration_years": 3,
        "notes": "ITF ceiling varies by programme",
    },
    "NSFC": {
        "max_total": 2_000_000,
        "max_equipment_pct": 0.30,
        "max_travel_pct": 0.15,
        "max_duration_years": 4,
        "notes": "NSFC joint scheme; amounts may be in RMB on Mainland side",
    },
}


def create_budget(
    db_path: str | Path,
    application_id: int,
    items: list[dict],
) -> list[int]:
    """Insert budget line items for an application.

    Args:
        db_path: Path to the grant_tracker database.
        application_id: FK to the applications table.
        items: List of dicts each with keys: category, description, year, amount,
               and optionally justification.

    Returns:
        List of newly created budget_item IDs.
    """
    ids: list[int] = []
    with get_db(db_path) as conn:
        for item in items:
            cur = conn.execute(
                """INSERT INTO budget_items (application_id, category, description, year, amount, justification)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    application_id,
                    item["category"],
                    item.get("description", ""),
                    item.get("year"),
                    item["amount"],
                    item.get("justification", ""),
                ),
            )
            ids.append(cur.lastrowid)  # type: ignore[arg-type]
    return ids


def get_budget_summary(db_path: str | Path, application_id: int) -> dict:
    """Return the budget grouped by category and year with totals.

    Returns a dict with keys:
        - ``by_category``: {category: total}
        - ``by_year``: {year: total}
        - ``by_category_year``: {category: {year: total}}
        - ``grand_total``: float
        - ``items``: list of all budget item dicts
    """
    with get_db(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM budget_items WHERE application_id = ? ORDER BY year, category",
            (application_id,),
        ).fetchall()

    items = [dict(r) for r in rows]
    by_category: dict[str, float] = {}
    by_year: dict[int | None, float] = {}
    by_category_year: dict[str, dict[int | None, float]] = {}

    for item in items:
        cat = item["category"]
        yr = item.get("year")
        amt = item.get("amount", 0) or 0

        by_category[cat] = by_category.get(cat, 0) + amt
        by_year[yr] = by_year.get(yr, 0) + amt
        by_category_year.setdefault(cat, {})
        by_category_year[cat][yr] = by_category_year[cat].get(yr, 0) + amt

    return {
        "by_category": by_category,
        "by_year": by_year,
        "by_category_year": by_category_year,
        "grand_total": sum(by_category.values()),
        "items": items,
    }


def validate_budget(items: list[dict], scheme_code: str) -> dict:
    """Check budget items against scheme funding limits.

    Args:
        items: List of budget item dicts (category, amount, year, ...).
        scheme_code: The scheme to validate against (e.g. "GRF").

    Returns:
        A dict with keys:
            - ``valid``: bool
            - ``warnings``: list of warning strings
            - ``errors``: list of error strings
            - ``total``: float
            - ``limit``: scheme limit info dict or None
    """
    normalised = scheme_code.upper().strip()
    limits = _SCHEME_LIMITS.get(normalised)
    warnings: list[str] = []
    errors: list[str] = []

    total = sum(i.get("amount", 0) or 0 for i in items)

    category_totals: dict[str, float] = {}
    for item in items:
        cat = item.get("category", "other")
        category_totals[cat] = category_totals.get(cat, 0) + (item.get("amount", 0) or 0)

    if not items:
        warnings.append("Budget is empty — no items provided.")

    for item in items:
        amt = item.get("amount", 0) or 0
        if amt <= 0:
            errors.append(f"Item '{item.get('description', '?')}' has non-positive amount: {amt}")
        if not item.get("category"):
            errors.append(f"Item '{item.get('description', '?')}' missing category.")
        cat = item.get("category", "")
        if cat and cat not in RGC_BUDGET_CATEGORIES:
            warnings.append(f"Non-standard category '{cat}' for item '{item.get('description', '?')}'.")

    salary_cats = ("ra_salary", "postdoc_salary")
    for cat in salary_cats:
        cat_total = category_totals.get(cat, 0)
        if cat_total > 0:
            role = "ra" if cat == "ra_salary" else "postdoc"
            norms = DEFAULT_SALARY_NORMS.get(role, {})
            high = norms.get("monthly_high", 0)
            if high > 0:
                annual_high = high * 12
                years = len({i.get("year") for i in items if i.get("category") == cat and i.get("year")}) or 1
                if cat_total / years > annual_high * 1.2:
                    warnings.append(
                        f"{cat} budget ({cat_total / years:,.0f}/yr) exceeds typical HK norms "
                        f"(~{high:,}/mo × 12 = {annual_high:,}/yr)."
                    )

    if limits:
        max_total = limits.get("max_total", float("inf"))
        if total > max_total:
            errors.append(
                f"Total budget HK${total:,.0f} exceeds {normalised} ceiling of HK${max_total:,.0f}."
            )

        for pct_key, cat_keys in [
            ("max_equipment_pct", ["equipment"]),
            ("max_travel_pct", ["travel"]),
        ]:
            max_pct = limits.get(pct_key)
            if max_pct and total > 0:
                cat_sum = sum(category_totals.get(c, 0) for c in cat_keys)
                actual_pct = cat_sum / total
                if actual_pct > max_pct:
                    label = pct_key.replace("max_", "").replace("_pct", "")
                    warnings.append(
                        f"{label.title()} is {actual_pct:.0%} of total, exceeding guideline of {max_pct:.0%}."
                    )

    return {
        "valid": len(errors) == 0,
        "warnings": warnings,
        "errors": errors,
        "total": total,
        "limit": limits,
    }
