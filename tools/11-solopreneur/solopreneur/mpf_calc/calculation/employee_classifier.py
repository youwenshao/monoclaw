"""Employee MPF eligibility classification.

Implements the 60-day exemption rule for new employees and determines
whether an employee is required to join an MPF scheme.
"""

from __future__ import annotations

from datetime import date, timedelta


_EXEMPTION_DAYS = 60


def is_within_60_day_rule(start_date: date, reference_date: date) -> bool:
    """Return True if the employee is still within the 60-day exemption period."""
    return (reference_date - start_date).days < _EXEMPTION_DAYS


def get_mpf_enrollment_date(start_date: date) -> date:
    """Return the date on which MPF enrollment becomes mandatory (start + 60 days)."""
    return start_date + timedelta(days=_EXEMPTION_DAYS)


def classify_employee(
    employment_type: str,
    start_date: date,
    reference_date: date,
) -> dict[str, object]:
    """Determine whether an employee is MPF-eligible at a reference date.

    Returns:
        Dict with ``mpf_eligible`` (bool) and ``reason`` (str).
    """
    if employment_type == "casual":
        days_employed = (reference_date - start_date).days
        if days_employed < _EXEMPTION_DAYS:
            return {
                "mpf_eligible": False,
                "reason": "Casual employee within 60-day exemption",
            }

    if is_within_60_day_rule(start_date, reference_date):
        enrollment_date = get_mpf_enrollment_date(start_date)
        return {
            "mpf_eligible": False,
            "reason": f"Within 60-day rule — enrollment due {enrollment_date.isoformat()}",
        }

    return {
        "mpf_eligible": True,
        "reason": "Enrolled",
    }
