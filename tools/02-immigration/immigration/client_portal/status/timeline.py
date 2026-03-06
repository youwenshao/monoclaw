"""Processing time estimation for immigration cases."""

from __future__ import annotations

from datetime import date, timedelta


def estimate_completion(
    scheme: str,
    submitted_date: str,
    config_times: dict[str, dict[str, int]],
    holidays: list[str],
) -> dict:
    """Estimate the completion date range for an immigration application.

    Args:
        scheme: Visa scheme code (GEP, ASMTP, QMAS, TTPS, IANG, Dependant).
        submitted_date: ISO date string of when the application was submitted.
        config_times: Mapping of scheme → {min: weeks, max: weeks}.
        holidays: List of ISO date strings for HK public holidays.

    Returns:
        Dict with estimated_min_date, estimated_max_date,
        business_days_elapsed, business_days_remaining.
    """
    submitted = date.fromisoformat(submitted_date)
    today = date.today()

    times = config_times.get(scheme, {"min": 4, "max": 8})
    min_weeks = times.get("min", 4)
    max_weeks = times.get("max", 8)

    holiday_set = {date.fromisoformat(h) for h in holidays}

    min_bdays = min_weeks * 5
    max_bdays = max_weeks * 5

    estimated_min = _add_business_days(submitted, min_bdays, holiday_set)
    estimated_max = _add_business_days(submitted, max_bdays, holiday_set)

    elapsed = _count_business_days(submitted, today, holiday_set)

    remaining_min = max(0, min_bdays - elapsed)
    remaining_max = max(0, max_bdays - elapsed)

    return {
        "estimated_min_date": estimated_min.isoformat(),
        "estimated_max_date": estimated_max.isoformat(),
        "business_days_elapsed": elapsed,
        "business_days_remaining_min": remaining_min,
        "business_days_remaining_max": remaining_max,
    }


def _is_business_day(d: date, holidays: set[date]) -> bool:
    return d.weekday() < 5 and d not in holidays


def _add_business_days(start: date, days: int, holidays: set[date]) -> date:
    """Add N business days to a start date, skipping weekends and holidays."""
    current = start
    added = 0
    while added < days:
        current += timedelta(days=1)
        if _is_business_day(current, holidays):
            added += 1
    return current


def _count_business_days(start: date, end: date, holidays: set[date]) -> int:
    """Count business days between two dates (exclusive of start, inclusive of end)."""
    if end <= start:
        return 0
    count = 0
    current = start
    while current < end:
        current += timedelta(days=1)
        if _is_business_day(current, holidays):
            count += 1
    return count
