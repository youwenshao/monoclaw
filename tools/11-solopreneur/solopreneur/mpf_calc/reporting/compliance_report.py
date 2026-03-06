"""MPF compliance tracking — deadlines, late payments, surcharges."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from openclaw_shared.database import get_db

from solopreneur.mpf_calc.calculation.mpf_engine import calculate_surcharge


def get_contribution_day_countdown() -> int:
    """Days remaining until the next contribution day (10th of next month)."""
    today = date.today()
    if today.day <= 10:
        next_deadline = today.replace(day=10)
    else:
        if today.month == 12:
            next_deadline = date(today.year + 1, 1, 10)
        else:
            next_deadline = date(today.year, today.month + 1, 10)
    return (next_deadline - today).days


def _next_contribution_deadline() -> date:
    today = date.today()
    if today.day <= 10:
        return today.replace(day=10)
    if today.month == 12:
        return date(today.year + 1, 1, 10)
    return date(today.year, today.month + 1, 10)


def get_compliance_status(db_path: str) -> dict[str, Any]:
    """High-level compliance dashboard data.

    Returns counts for on-time, late, and pending contributions,
    plus the next deadline date and countdown.
    """
    with get_db(db_path) as conn:
        paid = conn.execute(
            "SELECT COUNT(*) FROM monthly_contributions WHERE payment_status = 'paid'"
        ).fetchone()[0]
        late = conn.execute(
            "SELECT COUNT(*) FROM monthly_contributions WHERE payment_status = 'late'"
        ).fetchone()[0]
        pending = conn.execute(
            "SELECT COUNT(*) FROM monthly_contributions WHERE payment_status IN ('calculated', 'pending')"
        ).fetchone()[0]

    deadline = _next_contribution_deadline()
    countdown = get_contribution_day_countdown()

    return {
        "on_time_count": paid,
        "late_count": late,
        "pending_count": pending,
        "next_deadline": deadline.isoformat(),
        "days_until_deadline": countdown,
    }


def check_late_contributions(db_path: str) -> list[dict[str, Any]]:
    """Identify late contributions and compute surcharges."""
    results: list[dict[str, Any]] = []

    with get_db(db_path) as conn:
        rows = conn.execute(
            """SELECT mc.*, e.name_en
               FROM monthly_contributions mc
               JOIN employees e ON e.id = mc.employee_id
               WHERE mc.payment_status = 'late'
               ORDER BY mc.contribution_month DESC"""
        ).fetchall()

    for row in rows:
        r = dict(row)
        total = Decimal(str(r["total_contribution"]))
        surcharge = calculate_surcharge(total)
        r["calculated_surcharge"] = float(surcharge)
        results.append(r)

    return results
