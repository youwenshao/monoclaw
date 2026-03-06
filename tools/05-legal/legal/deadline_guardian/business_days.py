"""HK business day and public holiday calculator.

Hong Kong courts follow the General Holidays Ordinance (Cap 149).
If the last day of a procedural period falls on a Sunday or general
holiday, the period is extended to the next day that is neither.
Saturdays are also non-business days for court filing purposes.
"""

from __future__ import annotations

from datetime import date, timedelta

# HK General Holidays (Cap 149) — 17 per year.
# Lunar-calendar dates shift annually; this default set covers 2025-2027
# and should be supplemented via config.extra["public_holidays"].
DEFAULT_HK_HOLIDAYS: set[str] = {
    # ── 2025 ──────────────────────────────────────────────────────
    "2025-01-01",                                   # New Year's Day
    "2025-01-29", "2025-01-30", "2025-01-31",       # Lunar New Year
    "2025-04-04",                                   # Ching Ming
    "2025-04-18", "2025-04-19", "2025-04-21",       # Good Friday / Easter
    "2025-05-01",                                   # Labour Day
    "2025-05-05",                                   # Buddha's Birthday
    "2025-05-31",                                   # Tuen Ng (Dragon Boat)
    "2025-07-01",                                   # HKSAR Establishment Day
    "2025-10-01",                                   # National Day
    "2025-10-07",                                   # Day after Mid-Autumn
    "2025-10-29",                                   # Chung Yeung
    "2025-12-25", "2025-12-26",                     # Christmas
    # ── 2026 ──────────────────────────────────────────────────────
    "2026-01-01",                                   # New Year's Day
    "2026-02-17", "2026-02-18", "2026-02-19",       # Lunar New Year
    "2026-04-03", "2026-04-04", "2026-04-06",       # Good Friday / Easter
    "2026-04-05",                                   # Ching Ming
    "2026-05-01",                                   # Labour Day
    "2026-05-24",                                   # Buddha's Birthday
    "2026-06-19",                                   # Tuen Ng
    "2026-07-01",                                   # HKSAR Establishment Day
    "2026-09-26",                                   # Day after Mid-Autumn
    "2026-10-01",                                   # National Day
    "2026-10-18",                                   # Chung Yeung
    "2026-12-25", "2026-12-26",                     # Christmas
    # ── 2027 ──────────────────────────────────────────────────────
    "2027-01-01",                                   # New Year's Day
    "2027-02-06", "2027-02-07", "2027-02-08",       # Lunar New Year
    "2027-03-26", "2027-03-27", "2027-03-29",       # Good Friday / Easter
    "2027-04-05",                                   # Ching Ming
    "2027-05-01",                                   # Labour Day
    "2027-05-13",                                   # Buddha's Birthday
    "2027-06-09",                                   # Tuen Ng
    "2027-07-01",                                   # HKSAR Establishment Day
    "2027-09-16",                                   # Day after Mid-Autumn
    "2027-10-01",                                   # National Day
    "2027-10-08",                                   # Chung Yeung
    "2027-12-25", "2027-12-27",                     # Christmas (Dec 26 Sun → Dec 27)
}


def _holiday_set(holidays: list[str] | None) -> set[str]:
    """Resolve the effective holiday set from an optional config list."""
    if holidays is not None:
        return set(holidays)
    return DEFAULT_HK_HOLIDAYS


def is_business_day(d: date, holidays: list[str] | None = None) -> bool:
    """Return True if *d* is a business day (Mon-Fri, not a general holiday)."""
    if d.weekday() >= 5:
        return False
    return d.isoformat() not in _holiday_set(holidays)


def next_business_day(d: date, holidays: list[str] | None = None) -> date:
    """Return the earliest business day on or after *d*.

    If *d* is already a business day it is returned unchanged.
    """
    hols = _holiday_set(holidays)
    while d.weekday() >= 5 or d.isoformat() in hols:
        d += timedelta(days=1)
    return d


def add_business_days(start: date, days: int, holidays: list[str] | None = None) -> date:
    """Advance *days* business days forward from *start* (start date excluded)."""
    hols = _holiday_set(holidays)
    current = start
    added = 0
    while added < days:
        current += timedelta(days=1)
        if current.weekday() < 5 and current.isoformat() not in hols:
            added += 1
    return current


def add_calendar_days_with_rollover(
    start: date, days: int, holidays: list[str] | None = None
) -> date:
    """Add *days* calendar days to *start*.

    If the resulting date falls on a weekend or general holiday the
    deadline rolls forward to the next business day (per HK court
    practice).
    """
    result = start + timedelta(days=days)
    return next_business_day(result, holidays)
