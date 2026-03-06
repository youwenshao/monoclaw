"""Cash-flow forecasting from outstanding invoices."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
from typing import Any

from openclaw_shared.database import get_db


def forecast_cash_flow(
    db_path: str | Path, days_ahead: int = 90
) -> dict[str, Any]:
    """Project weekly cash inflows and outflows from outstanding invoices.

    Returns ``{"weeks": [{"week_start": …, "week_end": …, "inflows": …,
    "outflows": …, "net": …}, …]}``.
    """
    today = date.today()
    horizon = today + timedelta(days=days_ahead)

    with get_db(db_path) as conn:
        rows = conn.execute(
            """SELECT invoice_type, due_date, balance
               FROM invoices
               WHERE status NOT IN ('paid', 'written_off', 'draft')
                 AND due_date IS NOT NULL
                 AND due_date <= ?
               ORDER BY due_date""",
            (horizon.isoformat(),),
        ).fetchall()

    weeks: list[dict[str, Any]] = []
    week_start = today - timedelta(days=today.weekday())  # Monday
    while week_start <= horizon:
        week_end = week_start + timedelta(days=6)
        weeks.append({
            "week_start": week_start.isoformat(),
            "week_end": week_end.isoformat(),
            "inflows": 0.0,
            "outflows": 0.0,
            "net": 0.0,
        })
        week_start += timedelta(days=7)

    for row in rows:
        r = dict(row)
        try:
            due = date.fromisoformat(r["due_date"])
        except (ValueError, TypeError):
            continue

        balance = r.get("balance", 0.0) or 0.0
        for w in weeks:
            ws = date.fromisoformat(w["week_start"])
            we = date.fromisoformat(w["week_end"])
            if ws <= due <= we:
                if r["invoice_type"] == "receivable":
                    w["inflows"] += balance
                else:
                    w["outflows"] += balance
                break

    for w in weeks:
        w["inflows"] = round(w["inflows"], 2)
        w["outflows"] = round(w["outflows"], 2)
        w["net"] = round(w["inflows"] - w["outflows"], 2)

    return {"weeks": weeks}


def get_cash_flow_summary(db_path: str | Path) -> dict[str, Any]:
    """Aggregate inflows/outflows into 30/60/90-day totals."""
    today = date.today()

    buckets = {
        "30_day": {"inflows": 0.0, "outflows": 0.0, "net": 0.0},
        "60_day": {"inflows": 0.0, "outflows": 0.0, "net": 0.0},
        "90_day": {"inflows": 0.0, "outflows": 0.0, "net": 0.0},
    }

    with get_db(db_path) as conn:
        rows = conn.execute(
            """SELECT invoice_type, due_date, balance
               FROM invoices
               WHERE status NOT IN ('paid', 'written_off', 'draft')
                 AND due_date IS NOT NULL""",
        ).fetchall()

    for row in rows:
        r = dict(row)
        try:
            due = date.fromisoformat(r["due_date"])
        except (ValueError, TypeError):
            continue

        days_away = (due - today).days
        if days_away < 0:
            days_away = 0
        balance = r.get("balance", 0.0) or 0.0

        for limit, key in [(30, "30_day"), (60, "60_day"), (90, "90_day")]:
            if days_away <= limit:
                if r["invoice_type"] == "receivable":
                    buckets[key]["inflows"] += balance
                else:
                    buckets[key]["outflows"] += balance

    for b in buckets.values():
        b["inflows"] = round(b["inflows"], 2)
        b["outflows"] = round(b["outflows"], 2)
        b["net"] = round(b["inflows"] - b["outflows"], 2)

    return buckets
