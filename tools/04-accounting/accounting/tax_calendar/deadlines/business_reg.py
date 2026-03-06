"""Business Registration (BR) renewal deadline rules."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any


def calculate_br_renewal(client: dict, config: dict) -> list[dict]:
    """Calculate next BR renewal deadline.

    Business Registration Certificate must be renewed annually (or triennially)
    on the anniversary of the original registration date.
    Late renewal incurs a HK$300 penalty.
    """
    br_number = client.get("br_number")
    if not br_number:
        return []

    next_renewal = _next_renewal_date(client)
    fee_1yr = config.get("extra", {}).get("br_renewal_1yr_fee", 2250)
    fee_3yr = config.get("extra", {}).get("br_renewal_3yr_fee", 5950)

    deadline: dict[str, Any] = {
        "client_id": client["id"],
        "deadline_type": "business_registration",
        "form_code": "BR",
        "assessment_year": "",
        "original_due_date": next_renewal,
        "extended_due_date": None,
        "extension_type": None,
        "extension_status": None,
        "filing_status": "not_started",
        "notes": f"BR renewal. 1-year fee: HK${fee_1yr:,}, 3-year fee: HK${fee_3yr:,}. Late penalty: HK$300.",
    }
    return [deadline]


def _next_renewal_date(client: dict) -> date:
    """Determine next BR renewal date based on creation date or year-end convention.

    Falls back to using the year-end month as a proxy anniversary
    (common when exact registration date is unknown).
    """
    today = date.today()
    year_end_month = client.get("year_end_month", 3)

    anniversary = date(today.year, year_end_month, 1)
    if anniversary <= today:
        if year_end_month == 12:
            anniversary = date(today.year + 1, year_end_month, 1)
        else:
            anniversary = date(today.year + 1, year_end_month, 1)

    return anniversary


def late_penalty() -> float:
    """Fixed penalty for late BR renewal."""
    return 300.0


def renewal_fee(period: str = "1yr", config: dict | None = None) -> float:
    """Return the BR renewal fee for the given period."""
    cfg = config or {}
    extra = cfg.get("extra", {})
    if period == "3yr":
        return float(extra.get("br_renewal_3yr_fee", 5950))
    return float(extra.get("br_renewal_1yr_fee", 2250))
