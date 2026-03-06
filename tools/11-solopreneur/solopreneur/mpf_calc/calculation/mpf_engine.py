"""Core MPF contribution calculation engine.

Implements Hong Kong Mandatory Provident Fund rules with Decimal precision
for all monetary values.
"""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from openclaw_shared.database import get_db

CONTRIBUTION_RATE = Decimal("0.05")
MAX_RELEVANT_INCOME = Decimal("30000")
MIN_RELEVANT_INCOME = Decimal("7100")
MAX_MONTHLY_CONTRIBUTION = Decimal("1500")
LATE_SURCHARGE_RATE = Decimal("0.05")
TVC_ANNUAL_CAP = Decimal("60000")

_TWO_PLACES = Decimal("0.01")


def _round(value: Decimal) -> Decimal:
    return value.quantize(_TWO_PLACES, rounding=ROUND_HALF_UP)


def calculate_mandatory_contribution(
    relevant_income: Decimal,
) -> tuple[Decimal, Decimal]:
    """Return (employer_mandatory, employee_mandatory) for a given relevant income.

    Rules:
    - Below MIN_RELEVANT_INCOME: employer pays 5%, employee pays 0
    - Between MIN and MAX: both pay 5%
    - Above MAX: both capped at MAX_MONTHLY_CONTRIBUTION
    """
    if relevant_income <= Decimal("0"):
        return Decimal("0"), Decimal("0")

    employer = _round(min(relevant_income * CONTRIBUTION_RATE, MAX_MONTHLY_CONTRIBUTION))

    if relevant_income < MIN_RELEVANT_INCOME:
        employee = Decimal("0")
    else:
        employee = _round(
            min(relevant_income * CONTRIBUTION_RATE, MAX_MONTHLY_CONTRIBUTION)
        )

    return employer, employee


def calculate_contributions_for_employee(
    employee: dict[str, Any],
    payroll_record: dict[str, Any],
) -> dict[str, Any]:
    """Calculate full contribution breakdown for one employee and payroll record."""
    relevant_income = Decimal(str(payroll_record.get("total_relevant_income", 0)))
    employer_mandatory, employee_mandatory = calculate_mandatory_contribution(
        relevant_income
    )
    employer_vol = Decimal(str(payroll_record.get("employer_voluntary", 0)))
    employee_vol = Decimal(str(payroll_record.get("employee_voluntary", 0)))

    total = employer_mandatory + employee_mandatory + employer_vol + employee_vol

    return {
        "employee_id": employee["id"],
        "name_en": employee["name_en"],
        "name_tc": employee.get("name_tc", ""),
        "employment_type": employee.get("employment_type", ""),
        "relevant_income": float(relevant_income),
        "employer_mandatory": float(employer_mandatory),
        "employee_mandatory": float(employee_mandatory),
        "employer_voluntary": float(employer_vol),
        "employee_voluntary": float(employee_vol),
        "total_contribution": float(total),
    }


def calculate_monthly_all(
    db_path: str,
    contribution_month: str,
) -> list[dict[str, Any]]:
    """Calculate contributions for all active employees for a given month.

    Args:
        db_path: Path to the MPF database.
        contribution_month: YYYY-MM format string.

    Returns:
        List of contribution dicts per employee.
    """
    results: list[dict[str, Any]] = []

    with get_db(db_path) as conn:
        employees = [
            dict(r)
            for r in conn.execute(
                "SELECT * FROM employees WHERE active = 1"
            ).fetchall()
        ]

        for emp in employees:
            payroll = conn.execute(
                """SELECT * FROM payroll_records
                   WHERE employee_id = ?
                     AND strftime('%%Y-%%m', pay_period_start) = ?
                   ORDER BY id DESC LIMIT 1""",
                (emp["id"], contribution_month),
            ).fetchone()

            if payroll is None:
                ri = Decimal(str(emp.get("monthly_salary", 0)))
                payroll_dict: dict[str, Any] = {"total_relevant_income": float(ri)}
            else:
                payroll_dict = dict(payroll)

            result = calculate_contributions_for_employee(emp, payroll_dict)
            result["contribution_month"] = contribution_month
            results.append(result)

    return results


def calculate_surcharge(total_amount: Decimal) -> Decimal:
    """Calculate 5% surcharge on late MPF contributions."""
    return _round(total_amount * LATE_SURCHARGE_RATE)
