"""Tests for HK business day logic."""

from datetime import date

from legal.deadline_guardian.business_days import (
    add_business_days,
    add_calendar_days_with_rollover,
    is_business_day,
    next_business_day,
)

NO_HOLIDAYS: list[str] = []


def test_weekday_is_business_day():
    monday = date(2026, 3, 2)
    assert is_business_day(monday, NO_HOLIDAYS) is True


def test_saturday_not_business_day():
    saturday = date(2026, 3, 7)
    assert is_business_day(saturday, NO_HOLIDAYS) is False


def test_sunday_not_business_day():
    sunday = date(2026, 3, 8)
    assert is_business_day(sunday, NO_HOLIDAYS) is False


def test_holiday_not_business_day():
    hk_new_year = date(2026, 1, 1)
    assert is_business_day(hk_new_year) is False


def test_next_business_day_from_friday():
    saturday = date(2026, 3, 7)
    assert next_business_day(saturday, NO_HOLIDAYS) == date(2026, 3, 9)  # Monday


def test_next_business_day_from_holiday():
    """2026-12-25 is Friday (Christmas); 2026-12-26 is Saturday (also holiday)."""
    christmas = date(2026, 12, 25)
    result = next_business_day(christmas)
    assert result == date(2026, 12, 28)  # Monday


def test_add_business_days():
    monday = date(2026, 3, 2)
    result = add_business_days(monday, 5, NO_HOLIDAYS)
    assert result == date(2026, 3, 9)  # next Monday


def test_calendar_days_rollover():
    saturday = date(2026, 3, 7)
    result = add_calendar_days_with_rollover(saturday, 14, NO_HOLIDAYS)
    assert result == date(2026, 3, 23)  # 3/21 is Saturday → rolls to Monday 3/23
