"""Sales aggregation queries — daily, weekly, monthly summaries."""

from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from openclaw_shared.database import get_db


def get_daily_summary(db_path: str | Path, target_date: date | None = None) -> dict[str, Any]:
    """Revenue, transaction count, and average ticket for a single day."""
    d = (target_date or date.today()).isoformat()
    with get_db(db_path) as conn:
        row = conn.execute(
            """SELECT COALESCE(SUM(total_amount), 0) AS revenue,
                      COUNT(*) AS transactions,
                      COALESCE(AVG(total_amount), 0) AS avg_ticket
               FROM sales
               WHERE DATE(sale_date) = ?""",
            (d,),
        ).fetchone()
    return {
        "date": d,
        "revenue": row["revenue"],
        "transactions": row["transactions"],
        "avg_ticket": round(row["avg_ticket"], 2),
    }


def get_weekly_summary(db_path: str | Path, week_start: date | None = None) -> dict[str, Any]:
    """Aggregate a 7-day window starting from *week_start* (default: last Monday)."""
    if week_start is None:
        today = date.today()
        week_start = today - timedelta(days=today.weekday())
    week_end = week_start + timedelta(days=6)

    with get_db(db_path) as conn:
        row = conn.execute(
            """SELECT COALESCE(SUM(total_amount), 0) AS revenue,
                      COUNT(*) AS transactions,
                      COALESCE(AVG(total_amount), 0) AS avg_ticket
               FROM sales
               WHERE DATE(sale_date) BETWEEN ? AND ?""",
            (week_start.isoformat(), week_end.isoformat()),
        ).fetchone()

        daily_rows = conn.execute(
            """SELECT DATE(sale_date) AS day, COALESCE(SUM(total_amount), 0) AS revenue
               FROM sales
               WHERE DATE(sale_date) BETWEEN ? AND ?
               GROUP BY DATE(sale_date)
               ORDER BY day""",
            (week_start.isoformat(), week_end.isoformat()),
        ).fetchall()

    return {
        "week_start": week_start.isoformat(),
        "week_end": week_end.isoformat(),
        "revenue": row["revenue"],
        "transactions": row["transactions"],
        "avg_ticket": round(row["avg_ticket"], 2),
        "daily_breakdown": [dict(r) for r in daily_rows],
    }


def get_monthly_summary(db_path: str | Path, year: int, month: int) -> dict[str, Any]:
    """Aggregate revenue for a calendar month."""
    month_str = f"{year}-{month:02d}"
    with get_db(db_path) as conn:
        row = conn.execute(
            """SELECT COALESCE(SUM(total_amount), 0) AS revenue,
                      COUNT(*) AS transactions,
                      COALESCE(AVG(total_amount), 0) AS avg_ticket
               FROM sales
               WHERE strftime('%Y-%m', sale_date) = ?""",
            (month_str,),
        ).fetchone()

        weekly_rows = conn.execute(
            """SELECT strftime('%W', sale_date) AS week, COALESCE(SUM(total_amount), 0) AS revenue
               FROM sales
               WHERE strftime('%Y-%m', sale_date) = ?
               GROUP BY week ORDER BY week""",
            (month_str,),
        ).fetchall()

    return {
        "year": year,
        "month": month,
        "revenue": row["revenue"],
        "transactions": row["transactions"],
        "avg_ticket": round(row["avg_ticket"], 2),
        "weekly_breakdown": [dict(r) for r in weekly_rows],
    }


def get_revenue_by_payment_method(
    db_path: str | Path,
    start: date,
    end: date,
) -> list[dict[str, Any]]:
    """Group revenue by payment method within a date range."""
    with get_db(db_path) as conn:
        rows = conn.execute(
            """SELECT payment_method,
                      COALESCE(SUM(total_amount), 0) AS revenue,
                      COUNT(*) AS transactions
               FROM sales
               WHERE DATE(sale_date) BETWEEN ? AND ?
               GROUP BY payment_method
               ORDER BY revenue DESC""",
            (start.isoformat(), end.isoformat()),
        ).fetchall()
    return [dict(r) for r in rows]


def get_top_selling_items(
    db_path: str | Path,
    start: date,
    end: date,
    limit: int = 10,
) -> list[dict[str, Any]]:
    """Parse the JSON ``items`` column and rank by quantity sold."""
    with get_db(db_path) as conn:
        rows = conn.execute(
            "SELECT items FROM sales WHERE DATE(sale_date) BETWEEN ? AND ?",
            (start.isoformat(), end.isoformat()),
        ).fetchall()

    item_totals: dict[str, dict[str, Any]] = {}
    for row in rows:
        raw = row["items"]
        if not raw:
            continue
        try:
            items = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            continue
        for item in items:
            name = item.get("name", "Unknown")
            qty = int(item.get("quantity", 1))
            revenue = float(item.get("price", 0)) * qty
            if name in item_totals:
                item_totals[name]["quantity"] += qty
                item_totals[name]["revenue"] += revenue
            else:
                item_totals[name] = {"name": name, "quantity": qty, "revenue": revenue}

    ranked = sorted(item_totals.values(), key=lambda x: x["revenue"], reverse=True)
    return ranked[:limit]
