"""Annual MPF contribution summaries and IR56B formatting."""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from openclaw_shared.database import get_db

_TWO_PLACES = Decimal("0.01")


def generate_annual_summary(
    db_path: str,
    year: int,
) -> list[dict[str, Any]]:
    """Aggregate per-employee MPF totals for a calendar year.

    Returns:
        List of dicts, one per employee, with yearly totals for each
        contribution type.
    """
    with get_db(db_path) as conn:
        rows = conn.execute(
            """SELECT
                   e.id AS employee_id,
                   e.name_en,
                   e.name_tc,
                   e.hkid_last4,
                   e.employment_type,
                   COALESCE(SUM(mc.relevant_income), 0) AS total_income,
                   COALESCE(SUM(mc.employer_mandatory), 0) AS total_employer_mandatory,
                   COALESCE(SUM(mc.employee_mandatory), 0) AS total_employee_mandatory,
                   COALESCE(SUM(mc.employer_voluntary), 0) AS total_employer_voluntary,
                   COALESCE(SUM(mc.employee_voluntary), 0) AS total_employee_voluntary,
                   COALESCE(SUM(mc.total_contribution), 0) AS total_contributions,
                   COUNT(mc.id) AS months_contributed
               FROM employees e
               LEFT JOIN monthly_contributions mc
                   ON mc.employee_id = e.id
                  AND strftime('%%Y', mc.contribution_month) = ?
               WHERE e.active = 1
               GROUP BY e.id
               ORDER BY e.name_en""",
            (str(year),),
        ).fetchall()
    return [dict(r) for r in rows]


def format_for_ir56b(summary_data: list[dict[str, Any]]) -> dict[str, Any]:
    """Reshape annual summary into a structure suitable for IR56B filing.

    The IR56B is the employer's return of remuneration and pensions filed
    with the Hong Kong Inland Revenue Department.
    """
    employees = []
    grand_total_income = Decimal("0")
    grand_total_mpf = Decimal("0")

    for emp in summary_data:
        income = Decimal(str(emp["total_income"]))
        er_mandatory = Decimal(str(emp["total_employer_mandatory"]))
        ee_mandatory = Decimal(str(emp["total_employee_mandatory"]))
        total_mpf = er_mandatory + ee_mandatory

        grand_total_income += income
        grand_total_mpf += total_mpf

        employees.append({
            "name_en": emp["name_en"],
            "name_tc": emp.get("name_tc", ""),
            "hkid_last4": emp.get("hkid_last4", ""),
            "total_income": float(income.quantize(_TWO_PLACES, rounding=ROUND_HALF_UP)),
            "employer_mpf": float(er_mandatory.quantize(_TWO_PLACES, rounding=ROUND_HALF_UP)),
            "employee_mpf": float(ee_mandatory.quantize(_TWO_PLACES, rounding=ROUND_HALF_UP)),
            "total_mpf": float(total_mpf.quantize(_TWO_PLACES, rounding=ROUND_HALF_UP)),
        })

    tax_year = str(summary_data[0].get("year", "")) if summary_data else ""

    return {
        "tax_year": tax_year,
        "employees": employees,
        "grand_total_income": float(grand_total_income.quantize(_TWO_PLACES)),
        "grand_total_mpf": float(grand_total_mpf.quantize(_TWO_PLACES)),
    }
