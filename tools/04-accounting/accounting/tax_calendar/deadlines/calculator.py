"""HK tax deadline calculation engine."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from accounting.tax_calendar.deadlines.profits_tax import calculate_profits_tax
from accounting.tax_calendar.deadlines.employers_return import calculate_employers_return
from accounting.tax_calendar.deadlines.mpf import calculate_mpf_deadlines
from accounting.tax_calendar.deadlines.business_reg import calculate_br_renewal


def calculate_deadlines(client: dict, assessment_year: str, config: dict) -> list[dict]:
    """Calculate all tax deadlines for a client based on year-end month and IRD code."""
    year_end_month = client["year_end_month"]
    code = ird_code_category(year_end_month)
    holidays = config.get("extra", {}).get("public_holidays", [])

    deadlines: list[dict] = []
    deadlines.extend(calculate_profits_tax(client, code, assessment_year, config))
    deadlines.extend(calculate_employers_return(client, assessment_year, config))
    deadlines.extend(calculate_mpf_deadlines(client, assessment_year, config))
    deadlines.extend(calculate_br_renewal(client, config))

    for dl in deadlines:
        dl["original_due_date"] = adjust_for_holiday(dl["original_due_date"], holidays)
        if dl.get("extended_due_date"):
            dl["extended_due_date"] = adjust_for_holiday(dl["extended_due_date"], holidays)

    return deadlines


def ird_code_category(year_end_month: int) -> str:
    """Determine IRD code letter from accounting year-end month.

    D = December year-end
    M = March year-end
    N = all other year-ends
    """
    if year_end_month == 12:
        return "D"
    elif year_end_month == 3:
        return "M"
    else:
        return "N"


def adjust_for_holiday(due_date: date, holidays: list[str]) -> date:
    """If due date falls on a weekend or public holiday, shift to next business day."""
    if isinstance(due_date, str):
        due_date = date.fromisoformat(due_date)

    holiday_set = {date.fromisoformat(h) if isinstance(h, str) else h for h in holidays}

    while due_date.weekday() >= 5 or due_date in holiday_set:
        due_date += timedelta(days=1)

    return due_date


def parse_assessment_year(assessment_year: str) -> tuple[int, int]:
    """Parse '2025/26' into (2025, 2026)."""
    parts = assessment_year.split("/")
    start_year = int(parts[0])
    end_suffix = parts[1] if len(parts) > 1 else str(start_year + 1)[-2:]
    end_year = int(str(start_year)[:2] + end_suffix)
    return start_year, end_year


def effective_due_date(deadline: dict) -> date:
    """Return the effective due date considering any granted extensions."""
    extended = deadline.get("extended_due_date")
    original = deadline["original_due_date"]
    use = extended if extended and deadline.get("extension_status") == "granted" else original
    return date.fromisoformat(use) if isinstance(use, str) else use
