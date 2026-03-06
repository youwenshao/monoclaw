"""Birthday/anniversary tracker with lunar calendar conversion and gesture suggestions."""

from __future__ import annotations

import logging
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from lunardate import LunarDate

from openclaw_shared.database import get_db

logger = logging.getLogger("openclaw.fnb-hospitality.sommelier-memory.celebrations")

GESTURE_MAP: dict[str, dict[str, str]] = {
    "regular": {
        "birthday": "Complimentary dessert with candle",
        "anniversary": "Handwritten congratulations card",
    },
    "vip": {
        "birthday": "Complimentary birthday cake + house champagne toast",
        "anniversary": "Complimentary bottle of house wine + congratulations card",
    },
    "vvip": {
        "birthday": "Premium birthday cake + Dom Pérignon toast + personalised floral arrangement",
        "anniversary": "Chef's special tasting menu + premium wine pairing + personalised gift",
    },
}


def lunar_to_gregorian(lunar_month: int, lunar_day: int, year: int | None = None) -> date:
    """Convert a lunar month/day to the corresponding Gregorian date for the given year."""
    if year is None:
        year = date.today().year
    try:
        ld = LunarDate(year, lunar_month, lunar_day)
        return ld.toSolarDate()
    except ValueError:
        ld = LunarDate(year, lunar_month, min(lunar_day, 29))
        return ld.toSolarDate()


def _resolve_celebration_date(celebration: dict[str, Any], year: int) -> date | None:
    """Resolve a celebration record to a concrete Gregorian date for the given year."""
    if celebration.get("use_lunar") and celebration.get("lunar_date"):
        try:
            parts = str(celebration["lunar_date"]).split("-")
            lunar_month = int(parts[0])
            lunar_day = int(parts[1])
            return lunar_to_gregorian(lunar_month, lunar_day, year)
        except (ValueError, IndexError):
            logger.warning(
                "Invalid lunar date '%s' for celebration #%d",
                celebration.get("lunar_date"), celebration.get("id", 0),
            )
            return None

    if celebration.get("gregorian_date"):
        try:
            gd = celebration["gregorian_date"]
            if isinstance(gd, str):
                parts = gd.split("-")
                return date(year, int(parts[1]), int(parts[2]))
            return gd.replace(year=year)
        except (ValueError, IndexError, AttributeError):
            return None

    return None


def get_upcoming_celebrations(
    db_path: str | Path,
    lookahead_days: int = 7,
) -> list[dict[str, Any]]:
    """Return all celebrations occurring within the lookahead window.

    Each result includes the resolved Gregorian date, guest info, and a
    suggested gesture based on VIP tier.
    """
    today = date.today()
    end_date = today + timedelta(days=lookahead_days)

    with get_db(db_path) as conn:
        rows = conn.execute(
            """SELECT c.*, sg.name, sg.preferred_name, sg.phone, sg.vip_tier, sg.tags
               FROM celebrations c
               JOIN sm_guests sg ON sg.id = c.guest_id
               ORDER BY c.guest_id""",
        ).fetchall()

    results: list[dict[str, Any]] = []
    current_year = today.year

    for row in rows:
        cel = dict(row)
        resolved = _resolve_celebration_date(cel, current_year)

        if resolved is None:
            continue

        if resolved < today:
            resolved = _resolve_celebration_date(cel, current_year + 1)
            if resolved is None:
                continue

        if today <= resolved <= end_date:
            cel["resolved_date"] = resolved.isoformat()
            cel["days_until"] = (resolved - today).days
            cel["suggested_gesture"] = suggest_gesture(
                cel.get("vip_tier", "regular"),
                cel.get("event_type", "birthday"),
            )
            results.append(cel)

    results.sort(key=lambda x: x["resolved_date"])
    return results


def suggest_gesture(vip_tier: str, event_type: str) -> str:
    """Suggest an appropriate celebration gesture based on VIP tier and event type."""
    tier = vip_tier.lower() if vip_tier else "regular"
    event = event_type.lower() if event_type else "birthday"

    tier_gestures = GESTURE_MAP.get(tier, GESTURE_MAP["regular"])
    return tier_gestures.get(event, tier_gestures.get("birthday", "Complimentary dessert"))
