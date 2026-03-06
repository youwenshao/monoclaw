"""MPF contribution deadline reminders."""

from __future__ import annotations

from datetime import date
from typing import Any

from solopreneur.mpf_calc.reporting.compliance_report import (
    get_contribution_day_countdown,
)


def _next_deadline() -> date:
    today = date.today()
    if today.day <= 10:
        return today.replace(day=10)
    if today.month == 12:
        return date(today.year + 1, 1, 10)
    return date(today.year, today.month + 1, 10)


def get_upcoming_deadline() -> dict[str, Any]:
    """Return the next MPF contribution deadline and days remaining."""
    deadline = _next_deadline()
    return {
        "date": deadline.isoformat(),
        "days_until": get_contribution_day_countdown(),
    }


def should_send_reminder(contribution_day: int = 10, days_before: int = 3) -> bool:
    """Determine whether a reminder should fire today.

    Returns True when today falls within *days_before* of the contribution day.
    """
    countdown = get_contribution_day_countdown()
    return 0 < countdown <= days_before


_TEMPLATES = {
    "en": (
        "MPF Reminder: Contributions for this period are due on {date}. "
        "{days} day(s) remaining. Please arrange payment to avoid surcharge."
    ),
    "zh": (
        "強積金提醒：本期供款截止日期為 {date}。"
        "距離截止日尚餘 {days} 天，請安排繳付以免附加費。"
    ),
}


def format_reminder_message(
    deadline_info: dict[str, Any],
    language: str = "en",
) -> str:
    """Render a human-readable reminder message."""
    template = _TEMPLATES.get(language, _TEMPLATES["en"])
    return template.format(
        date=deadline_info["date"],
        days=deadline_info["days_until"],
    )
