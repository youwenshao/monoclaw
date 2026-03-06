"""Cash-flow analysis and forecasting for small-business owners."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
from typing import Any

from openclaw_shared.database import get_db


def get_cash_flow(
    db_path: str | Path,
    start_date: str,
    end_date: str,
) -> dict[str, Any]:
    """Cash inflows vs outflows within a date range.

    Returns daily-level breakdown plus totals.
    """
    with get_db(db_path) as conn:
        inflow_rows = conn.execute(
            """SELECT DATE(sale_date) AS day, COALESCE(SUM(total_amount), 0) AS amount
               FROM sales
               WHERE DATE(sale_date) BETWEEN ? AND ?
               GROUP BY DATE(sale_date)
               ORDER BY day""",
            (start_date, end_date),
        ).fetchall()

        outflow_rows = conn.execute(
            """SELECT expense_date AS day, COALESCE(SUM(amount), 0) AS amount
               FROM expenses
               WHERE expense_date BETWEEN ? AND ?
               GROUP BY expense_date
               ORDER BY day""",
            (start_date, end_date),
        ).fetchall()

        total_in_row = conn.execute(
            """SELECT COALESCE(SUM(total_amount), 0) AS total
               FROM sales WHERE DATE(sale_date) BETWEEN ? AND ?""",
            (start_date, end_date),
        ).fetchone()

        total_out_row = conn.execute(
            """SELECT COALESCE(SUM(amount), 0) AS total
               FROM expenses WHERE expense_date BETWEEN ? AND ?""",
            (start_date, end_date),
        ).fetchone()

    total_inflow = total_in_row["total"]
    total_outflow = total_out_row["total"]

    return {
        "start_date": start_date,
        "end_date": end_date,
        "total_inflow": round(total_inflow, 2),
        "total_outflow": round(total_outflow, 2),
        "net_cash_flow": round(total_inflow - total_outflow, 2),
        "daily_inflows": [dict(r) for r in inflow_rows],
        "daily_outflows": [dict(r) for r in outflow_rows],
    }


def get_cash_position(db_path: str | Path) -> dict[str, Any]:
    """Snapshot: all-time inflows minus all-time outflows."""
    with get_db(db_path) as conn:
        total_in = conn.execute(
            "SELECT COALESCE(SUM(total_amount), 0) AS total FROM sales"
        ).fetchone()["total"]
        total_out = conn.execute(
            "SELECT COALESCE(SUM(amount), 0) AS total FROM expenses"
        ).fetchone()["total"]

        today_in = conn.execute(
            "SELECT COALESCE(SUM(total_amount), 0) AS total FROM sales WHERE DATE(sale_date) = DATE('now')"
        ).fetchone()["total"]
        today_out = conn.execute(
            "SELECT COALESCE(SUM(amount), 0) AS total FROM expenses WHERE expense_date = DATE('now')"
        ).fetchone()["total"]

    return {
        "total_inflow": round(total_in, 2),
        "total_outflow": round(total_out, 2),
        "cash_position": round(total_in - total_out, 2),
        "today_inflow": round(today_in, 2),
        "today_outflow": round(today_out, 2),
    }


def forecast_cash_flow(
    db_path: str | Path,
    days_ahead: int = 30,
) -> dict[str, Any]:
    """Naive forecast based on average daily cash flow over the last 30 days.

    Projects the cash position forward by *days_ahead* days.
    """
    today = date.today()
    lookback_start = (today - timedelta(days=30)).isoformat()
    today_str = today.isoformat()

    with get_db(db_path) as conn:
        avg_in = conn.execute(
            """SELECT COALESCE(SUM(total_amount), 0) / 30.0 AS avg_daily
               FROM sales WHERE DATE(sale_date) BETWEEN ? AND ?""",
            (lookback_start, today_str),
        ).fetchone()["avg_daily"]

        avg_out = conn.execute(
            """SELECT COALESCE(SUM(amount), 0) / 30.0 AS avg_daily
               FROM expenses WHERE expense_date BETWEEN ? AND ?""",
            (lookback_start, today_str),
        ).fetchone()["avg_daily"]

    position = get_cash_position(db_path)
    current = position["cash_position"]
    daily_net = avg_in - avg_out

    forecast: list[dict[str, Any]] = []
    running = current
    for i in range(1, days_ahead + 1):
        running += daily_net
        forecast.append({
            "date": (today + timedelta(days=i)).isoformat(),
            "projected_position": round(running, 2),
        })

    return {
        "current_position": current,
        "avg_daily_inflow": round(avg_in, 2),
        "avg_daily_outflow": round(avg_out, 2),
        "avg_daily_net": round(daily_net, 2),
        "forecast": forecast,
    }
