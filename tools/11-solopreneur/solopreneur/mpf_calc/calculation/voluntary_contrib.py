"""Voluntary MPF contribution tracking and TVC cap enforcement."""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from openclaw_shared.database import get_db

from solopreneur.mpf_calc.calculation.mpf_engine import TVC_ANNUAL_CAP

_TWO_PLACES = Decimal("0.01")


def record_voluntary_contribution(
    db_path: str,
    employee_id: int,
    month: str,
    employer_vol: Decimal,
    employee_vol: Decimal,
) -> None:
    """Update voluntary contribution fields for an existing monthly record."""
    with get_db(db_path) as conn:
        conn.execute(
            """UPDATE monthly_contributions
               SET employer_voluntary = ?,
                   employee_voluntary = ?,
                   total_contribution = employer_mandatory + employee_mandatory + ? + ?
               WHERE employee_id = ?
                 AND strftime('%%Y-%%m', contribution_month) = ?""",
            (
                float(employer_vol),
                float(employee_vol),
                float(employer_vol),
                float(employee_vol),
                employee_id,
                month,
            ),
        )


def get_tvc_ytd(db_path: str, employee_id: int, year: int) -> Decimal:
    """Sum employee voluntary contributions for a calendar year."""
    with get_db(db_path) as conn:
        row = conn.execute(
            """SELECT COALESCE(SUM(employee_voluntary), 0) AS total
               FROM monthly_contributions
               WHERE employee_id = ?
                 AND strftime('%%Y', contribution_month) = ?""",
            (employee_id, str(year)),
        ).fetchone()
    return Decimal(str(row["total"])).quantize(_TWO_PLACES, rounding=ROUND_HALF_UP)


def check_tvc_cap(
    db_path: str,
    employee_id: int,
    year: int,
    proposed_amount: Decimal,
) -> dict[str, Any]:
    """Check if a proposed TVC amount stays within the annual cap.

    Returns:
        Dict with ``within_cap`` (bool) and ``remaining`` (Decimal).
    """
    ytd = get_tvc_ytd(db_path, employee_id, year)
    remaining = TVC_ANNUAL_CAP - ytd
    within = proposed_amount <= remaining
    return {
        "within_cap": within,
        "remaining": float(remaining),
        "ytd": float(ytd),
        "proposed": float(proposed_amount),
    }
