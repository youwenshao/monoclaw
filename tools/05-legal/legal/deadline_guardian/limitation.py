"""Cap 347 Limitation Ordinance period calculator.

Implements the core limitation periods under the Limitation Ordinance
(Cap 347, Laws of Hong Kong) for the most common civil claim types.
"""

from __future__ import annotations

from datetime import date

from legal.deadline_guardian.business_days import next_business_day

LIMITATION_PERIODS: dict[str, dict] = {
    "contract": {
        "years": 6,
        "section": "Cap 347 s.4",
        "description": "Simple contract — 6-year limitation period",
    },
    "personal_injury": {
        "years": 3,
        "section": "Cap 347 s.4A",
        "description": "Personal injury — 3-year limitation period",
    },
    "defamation": {
        "years": 1,
        "section": "Cap 347 s.27",
        "description": "Defamation — 1-year limitation period",
    },
    "latent_damage": {
        "years": 3,
        "section": "Cap 347 s.4C",
        "description": "Latent damage — 3 years from date of discoverability",
    },
}


def _add_years(d: date, years: int) -> date:
    """Add *years* to a date, clamping Feb 29 → Feb 28 in non-leap years."""
    try:
        return d.replace(year=d.year + years)
    except ValueError:
        return d.replace(year=d.year + years, day=28)


def calculate_limitation(
    claim_type: str,
    accrual_date: date,
    holidays: list[str] | None = None,
) -> dict:
    """Calculate the limitation expiry for *claim_type* from *accrual_date*.

    The raw calendar deadline is adjusted so that if it falls on a
    non-business day the effective deadline is the next business day.

    Returns a dict with:
      - claim_type, accrual_date, deadline_date, raw_deadline
      - statutory_basis, description, limitation_years
      - days_remaining (from today)
      - warning: EXPIRED | CRITICAL (≤90d) | WARNING (≤180d) | None
    """
    period = LIMITATION_PERIODS.get(claim_type)
    if period is None:
        raise ValueError(
            f"Unknown claim type '{claim_type}'. "
            f"Supported: {', '.join(LIMITATION_PERIODS)}"
        )

    raw_deadline = _add_years(accrual_date, period["years"])
    deadline_date = next_business_day(raw_deadline, holidays)
    days_remaining = (deadline_date - date.today()).days

    if days_remaining <= 0:
        warning = "EXPIRED"
    elif days_remaining <= 90:
        warning = "CRITICAL"
    elif days_remaining <= 180:
        warning = "WARNING"
    else:
        warning = None

    return {
        "claim_type": claim_type,
        "accrual_date": accrual_date.isoformat(),
        "deadline_date": deadline_date.isoformat(),
        "raw_deadline": raw_deadline.isoformat(),
        "statutory_basis": period["section"],
        "description": period["description"],
        "limitation_years": period["years"],
        "days_remaining": days_remaining,
        "warning": warning,
    }
