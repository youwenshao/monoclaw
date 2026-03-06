"""MPF (Mandatory Provident Fund) contribution deadline rules."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any


def calculate_mpf_deadlines(
    client: dict, assessment_year: str, config: dict
) -> list[dict]:
    """Calculate monthly MPF contribution deadlines for the assessment year.

    - Contributions due on the "contribution day" of the following month
      (typically the 10th, configurable).
    - Late payment incurs a 5% surcharge on outstanding contributions.
    - New employees must be enrolled within 60 days of employment start.
    """
    contribution_day = config.get("extra", {}).get("mpf_contribution_day", 10)

    parts = assessment_year.split("/")
    start_year = int(parts[0])
    end_suffix = parts[1] if len(parts) > 1 else str(start_year + 1)[-2:]
    end_year = int(str(start_year)[:2] + end_suffix)

    deadlines: list[dict] = []
    current = date(start_year, 4, 1)
    end = date(end_year, 3, 31)

    while current <= end:
        period_month = current
        due_date = _contribution_due_date(current, contribution_day)

        dl: dict[str, Any] = {
            "client_id": client["id"],
            "deadline_type": "mpf_contribution",
            "form_code": "MPF",
            "assessment_year": assessment_year,
            "original_due_date": due_date,
            "extended_due_date": None,
            "extension_type": None,
            "extension_status": None,
            "filing_status": "not_started",
            "notes": f"MPF contribution for {period_month.strftime('%B %Y')}",
            "_mpf_meta": {
                "period_month": period_month.isoformat(),
                "contribution_due_date": due_date.isoformat(),
                "surcharge_rate": 0.05,
            },
        }
        deadlines.append(dl)

        if current.month == 12:
            current = current.replace(year=current.year + 1, month=1)
        else:
            current = current.replace(month=current.month + 1)

    return deadlines


def _contribution_due_date(period_month: date, contribution_day: int = 10) -> date:
    """MPF contribution for a given month is due on the contribution_day of the following month."""
    if period_month.month == 12:
        following = date(period_month.year + 1, 1, contribution_day)
    else:
        following = date(period_month.year, period_month.month + 1, contribution_day)
    return following


def new_employee_enrolment_deadline(employment_start: date) -> date:
    """New employee must be enrolled in MPF scheme within 60 days of start."""
    return employment_start + timedelta(days=60)


def surcharge_amount(contribution_due: float, is_late: bool) -> float:
    """Calculate 5% surcharge on late MPF contributions."""
    if not is_late:
        return 0.0
    return round(contribution_due * 0.05, 2)


def mpf_status(due_date: date, paid: bool, paid_date: date | None = None) -> dict[str, Any]:
    """Determine MPF payment status and any surcharge liability."""
    today = date.today()
    if paid:
        late = paid_date is not None and paid_date > due_date
        return {"status": "paid", "late": late}
    if due_date < today:
        days_overdue = (today - due_date).days
        return {"status": "overdue", "days_overdue": days_overdue, "surcharge_applies": True}
    days_until = (due_date - today).days
    return {"status": "pending", "days_until_due": days_until}
