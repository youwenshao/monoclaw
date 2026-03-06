"""Payroll processing — record monthly income components and compute net pay."""

from __future__ import annotations

from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from openclaw_shared.database import get_db

from solopreneur.mpf_calc.calculation.income_rules import compute_relevant_income
from solopreneur.mpf_calc.calculation.mpf_engine import calculate_mandatory_contribution

_TWO_PLACES = Decimal("0.01")


def compute_net_pay(total_income: Decimal, employee_mpf_deduction: Decimal) -> Decimal:
    """Net pay = gross relevant income minus employee mandatory MPF."""
    return (total_income - employee_mpf_deduction).quantize(
        _TWO_PLACES, rounding=ROUND_HALF_UP
    )


def process_monthly_payroll(
    db_path: str,
    employee_id: int,
    month: str,
    income_components: dict[str, float],
) -> dict[str, Any]:
    """Create a payroll record for an employee for a given month.

    Args:
        db_path: Path to MPF database.
        employee_id: Employee id.
        month: YYYY-MM string.
        income_components: Keys include basic_salary, overtime, commission,
            bonus, other_income.

    Returns:
        The inserted payroll record as a dict.
    """
    basic = Decimal(str(income_components.get("basic_salary", 0)))
    overtime = Decimal(str(income_components.get("overtime", 0)))
    commission = Decimal(str(income_components.get("commission", 0)))
    bonus = Decimal(str(income_components.get("bonus", 0)))
    other = Decimal(str(income_components.get("other_income", 0)))

    total_ri = compute_relevant_income(basic, overtime, commission, bonus, other)
    _, employee_mpf = calculate_mandatory_contribution(total_ri)
    net = compute_net_pay(total_ri, employee_mpf)

    year, mon = month.split("-")
    period_start = date(int(year), int(mon), 1)
    if int(mon) == 12:
        period_end = date(int(year) + 1, 1, 1)
    else:
        period_end = date(int(year), int(mon) + 1, 1)
    from datetime import timedelta

    period_end = period_end - timedelta(days=1)

    with get_db(db_path) as conn:
        cursor = conn.execute(
            """INSERT INTO payroll_records
               (employee_id, pay_period_start, pay_period_end,
                basic_salary, overtime, commission, bonus, other_income,
                total_relevant_income, mpf_employee_deduction, net_pay)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                employee_id,
                period_start.isoformat(),
                period_end.isoformat(),
                float(basic),
                float(overtime),
                float(commission),
                float(bonus),
                float(other),
                float(total_ri),
                float(employee_mpf),
                float(net),
            ),
        )
        row = conn.execute(
            "SELECT * FROM payroll_records WHERE id = ?", (cursor.lastrowid,)
        ).fetchone()
    return dict(row)


def get_payroll_for_month(db_path: str, month: str) -> list[dict[str, Any]]:
    """Return all payroll records whose pay period starts in *month* (YYYY-MM)."""
    with get_db(db_path) as conn:
        rows = conn.execute(
            """SELECT pr.*, e.name_en, e.name_tc
               FROM payroll_records pr
               JOIN employees e ON e.id = pr.employee_id
               WHERE strftime('%%Y-%%m', pr.pay_period_start) = ?
               ORDER BY e.name_en""",
            (month,),
        ).fetchall()
    return [dict(r) for r in rows]
