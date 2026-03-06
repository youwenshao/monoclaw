"""Stamp duty calculator for Hong Kong tenancy agreements.

Rates follow the Inland Revenue Department schedule (configurable via
*rates* parameter to accommodate annual Budget changes).
"""

from __future__ import annotations

import math
from typing import Any

DEFAULT_RATES: list[dict[str, Any]] = [
    {
        "max_term_years": 1,
        "rate": 0.0025,
        "description": "Not exceeding 1 year: 0.25% of total rent",
    },
    {
        "max_term_years": 3,
        "rate": 0.005,
        "description": "Exceeding 1 year but not 3 years: 0.5% of average yearly rent",
    },
    {
        "max_term_years": 999,
        "rate": 0.01,
        "description": "Exceeding 3 years: 1% of average yearly rent",
    },
]


def calculate_stamp_duty(
    monthly_rent: int,
    term_months: int,
    rates: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Return a full stamp duty breakdown for a residential tenancy.

    Parameters
    ----------
    monthly_rent:
        Monthly rent in HKD.
    term_months:
        Duration of the tenancy in months.
    rates:
        Optional list of rate bands. Each dict should contain
        ``max_term_years`` (int), ``rate`` (float) and ``description``.
        Falls back to the current IRD default schedule when *None*.

    Returns
    -------
    dict with ``total_rent``, ``average_yearly_rent``, ``rate_applied``,
    ``duty_amount``, and ``breakdown``.
    """
    if monthly_rent <= 0 or term_months <= 0:
        return {
            "total_rent": 0,
            "average_yearly_rent": 0,
            "rate_applied": 0,
            "duty_amount": 0,
            "breakdown": "Invalid inputs: rent and term must be positive.",
        }

    bands = rates or DEFAULT_RATES
    total_rent = monthly_rent * term_months
    term_years = term_months / 12
    average_yearly_rent = total_rent / term_years if term_years else 0

    rate_applied = 0.0
    description = ""
    base_amount = 0.0

    for band in sorted(bands, key=lambda b: b["max_term_years"]):
        if term_years <= band["max_term_years"]:
            rate_applied = band["rate"]
            description = band["description"]
            if band["max_term_years"] <= 1:
                base_amount = total_rent
            else:
                base_amount = average_yearly_rent
            break

    duty_amount = math.ceil(base_amount * rate_applied)

    return {
        "total_rent": total_rent,
        "average_yearly_rent": round(average_yearly_rent, 2),
        "term_years": round(term_years, 2),
        "rate_applied": rate_applied,
        "duty_amount": duty_amount,
        "breakdown": (
            f"Term: {term_months} months ({term_years:.2f} years). "
            f"Total rent: HK${total_rent:,}. "
            f"Average yearly rent: HK${average_yearly_rent:,.2f}. "
            f"Rate: {rate_applied * 100:.2f}% — {description}. "
            f"Stamp duty payable: HK${duty_amount:,}."
        ),
    }
