"""Generate remittance statements for MPF trustee submissions."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from openclaw_shared.database import get_db

_TWO_PLACES = Decimal("0.01")


def get_remittance_data(
    db_path: str,
    contribution_month: str,
) -> list[dict[str, Any]]:
    """Fetch per-employee contribution rows for a given month."""
    with get_db(db_path) as conn:
        rows = conn.execute(
            """SELECT mc.*, e.name_en, e.name_tc, e.hkid_last4,
                      e.mpf_member_number, e.employment_type
               FROM monthly_contributions mc
               JOIN employees e ON e.id = mc.employee_id
               WHERE strftime('%%Y-%%m', mc.contribution_month) = ?
               ORDER BY e.name_en""",
            (contribution_month,),
        ).fetchall()
    return [dict(r) for r in rows]


def generate_remittance(
    db_path: str,
    contribution_month: str,
    trustee: str = "",
) -> dict[str, Any]:
    """Build a complete remittance statement dict.

    Args:
        db_path: Path to MPF database.
        contribution_month: YYYY-MM format.
        trustee: Name of MPF trustee / scheme.

    Returns:
        Dict containing header info and line-item employee contributions.
    """
    items = get_remittance_data(db_path, contribution_month)

    total_employer = Decimal("0")
    total_employee = Decimal("0")

    for item in items:
        total_employer += Decimal(str(item.get("employer_mandatory", 0))) + Decimal(
            str(item.get("employer_voluntary", 0))
        )
        total_employee += Decimal(str(item.get("employee_mandatory", 0))) + Decimal(
            str(item.get("employee_voluntary", 0))
        )

    total_amount = (total_employer + total_employee).quantize(
        _TWO_PLACES, rounding=ROUND_HALF_UP
    )

    with get_db(db_path) as conn:
        cursor = conn.execute(
            """INSERT INTO remittance_submissions
               (contribution_month, trustee, total_employer, total_employee,
                total_amount, employee_count, submitted_date, status)
               VALUES (?, ?, ?, ?, ?, ?, ?, 'draft')""",
            (
                f"{contribution_month}-01",
                trustee,
                float(total_employer),
                float(total_employee),
                float(total_amount),
                len(items),
                date.today().isoformat(),
            ),
        )
        submission_id = cursor.lastrowid

    return {
        "submission_id": submission_id,
        "contribution_month": contribution_month,
        "trustee": trustee,
        "total_employer": float(total_employer),
        "total_employee": float(total_employee),
        "total_amount": float(total_amount),
        "employee_count": len(items),
        "generated_at": datetime.now().isoformat(),
        "items": items,
    }
