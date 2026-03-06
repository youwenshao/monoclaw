"""Profit & Loss report generation with HK profits-tax estimation."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from openclaw_shared.database import get_db

# HK two-tier profits tax (unincorporated business)
_TIER1_THRESHOLD = 2_000_000.0
_TIER1_RATE = 0.0825
_TIER2_RATE = 0.165


def _estimate_hk_profits_tax(assessable_profit: float) -> float:
    """Two-tier HK profits tax: 8.25 % on first HK$2 M, 16.5 % thereafter."""
    if assessable_profit <= 0:
        return 0.0
    if assessable_profit <= _TIER1_THRESHOLD:
        return round(assessable_profit * _TIER1_RATE, 2)
    return round(
        _TIER1_THRESHOLD * _TIER1_RATE
        + (assessable_profit - _TIER1_THRESHOLD) * _TIER2_RATE,
        2,
    )


def generate_pnl(db_path: str | Path, year: int, month: int) -> dict[str, Any]:
    """Build a monthly P&L statement.

    Returns::

        {
            "year": int,
            "month": int,
            "revenue": float,
            "cost_of_goods": float,
            "gross_profit": float,
            "expenses_by_category": {category: amount, ...},
            "total_expenses": float,
            "net_profit": float,
            "estimated_tax": float,
        }
    """
    month_str = f"{year}-{month:02d}"

    with get_db(db_path) as conn:
        rev_row = conn.execute(
            """SELECT COALESCE(SUM(total_amount), 0) AS revenue
               FROM sales
               WHERE strftime('%Y-%m', sale_date) = ?""",
            (month_str,),
        ).fetchone()
        revenue: float = rev_row["revenue"]

        cogs_row = conn.execute(
            """SELECT COALESCE(SUM(amount), 0) AS cogs
               FROM expenses
               WHERE strftime('%Y-%m', expense_date) = ?
                 AND category = 'inventory'""",
            (month_str,),
        ).fetchone()
        cost_of_goods: float = cogs_row["cogs"]

        exp_rows = conn.execute(
            """SELECT category, COALESCE(SUM(amount), 0) AS total
               FROM expenses
               WHERE strftime('%Y-%m', expense_date) = ?
               GROUP BY category""",
            (month_str,),
        ).fetchall()

    expenses_by_category: dict[str, float] = {}
    total_expenses = 0.0
    for row in exp_rows:
        cat = row["category"] or "other"
        amt = row["total"]
        expenses_by_category[cat] = round(amt, 2)
        total_expenses += amt

    gross_profit = revenue - cost_of_goods
    net_profit = revenue - total_expenses
    estimated_tax = _estimate_hk_profits_tax(net_profit)

    return {
        "year": year,
        "month": month,
        "revenue": round(revenue, 2),
        "cost_of_goods": round(cost_of_goods, 2),
        "gross_profit": round(gross_profit, 2),
        "expenses_by_category": expenses_by_category,
        "total_expenses": round(total_expenses, 2),
        "net_profit": round(net_profit, 2),
        "estimated_tax": estimated_tax,
    }
