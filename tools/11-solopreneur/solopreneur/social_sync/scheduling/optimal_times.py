"""HK-market optimal posting time recommendations.

Based on typical Hong Kong social-media engagement patterns:
lunch break, evening commute, prime evening, and late-night scrolling.
"""

from __future__ import annotations

from datetime import datetime, time, timedelta

HK_OPTIMAL_TIMES: dict[str, tuple[int, int, int, int]] = {
    "lunch": (12, 0, 13, 0),
    "evening": (18, 0, 19, 0),
    "prime": (20, 0, 22, 0),
    "late_night": (22, 0, 0, 0),
}

_WEEKDAY_PREFS: dict[int, list[str]] = {
    0: ["lunch", "prime"],        # Monday
    1: ["lunch", "prime"],        # Tuesday
    2: ["lunch", "evening"],      # Wednesday
    3: ["lunch", "prime"],        # Thursday
    4: ["evening", "prime"],      # Friday
    5: ["lunch", "prime", "late_night"],  # Saturday
    6: ["lunch", "evening", "prime"],     # Sunday
}

_CONTENT_TYPE_PREFS: dict[str, str] = {
    "promo": "lunch",
    "lifestyle": "prime",
    "food": "lunch",
    "behind_the_scenes": "evening",
    "announcement": "lunch",
    "story": "late_night",
}


def _slot_start(slot_name: str, base_date: datetime | None = None) -> datetime:
    """Return a datetime for the start of a named time slot."""
    h_start, m_start, _, _ = HK_OPTIMAL_TIMES[slot_name]
    base = base_date or datetime.now()

    if h_start == 0 and slot_name == "late_night":
        target_date = base.date() + timedelta(days=1)
        return datetime.combine(target_date, time(0, 0))

    return base.replace(hour=h_start, minute=m_start, second=0, microsecond=0)


def get_next_optimal_time(current_time: datetime | None = None) -> datetime:
    """Return the nearest future optimal posting time from *current_time*.

    Walks through today's (and tomorrow's) slots to find the soonest one.
    """
    now = current_time or datetime.now()
    dow = now.weekday()
    preferred = _WEEKDAY_PREFS.get(dow, ["lunch", "prime"])

    for slot in preferred:
        candidate = _slot_start(slot, now)
        if candidate > now:
            return candidate

    tomorrow = now + timedelta(days=1)
    tomorrow_dow = tomorrow.weekday()
    tomorrow_preferred = _WEEKDAY_PREFS.get(tomorrow_dow, ["lunch", "prime"])
    first_slot = tomorrow_preferred[0]

    h_start, m_start, _, _ = HK_OPTIMAL_TIMES[first_slot]
    return datetime.combine(
        tomorrow.date(), time(h_start, m_start)
    )


def suggest_posting_time(
    day_of_week: int,
    content_type: str | None = None,
) -> datetime:
    """Suggest the best posting time for a given day and optional content type.

    Args:
        day_of_week: 0=Monday … 6=Sunday.
        content_type: Optional hint (e.g. "promo", "food", "lifestyle").

    Returns:
        A datetime for the next occurrence of *day_of_week* at the best slot.
    """
    today = datetime.now()
    days_ahead = (day_of_week - today.weekday()) % 7
    if days_ahead == 0 and today.hour >= 22:
        days_ahead = 7
    target_date = today + timedelta(days=days_ahead)

    slot = "prime"
    if content_type and content_type.lower() in _CONTENT_TYPE_PREFS:
        slot = _CONTENT_TYPE_PREFS[content_type.lower()]
    else:
        preferred = _WEEKDAY_PREFS.get(day_of_week, ["prime"])
        slot = preferred[0]

    h_start, m_start, _, _ = HK_OPTIMAL_TIMES[slot]
    if h_start == 0 and slot == "late_night":
        return datetime.combine(target_date.date() + timedelta(days=1), time(0, 0))

    return datetime.combine(target_date.date(), time(h_start, m_start))
