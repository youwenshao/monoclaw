"""Content calendar management with pre-loaded HK seasonal events."""

from __future__ import annotations

import json
import logging
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from openclaw_shared.database import get_db

logger = logging.getLogger(__name__)

HK_EVENTS: list[dict[str, Any]] = [
    {"month": 1, "day": 1, "name": "New Year's Day", "theme": "New Year promos"},
    {"month": 2, "day": 14, "name": "Valentine's Day", "theme": "Couple specials"},
    {"month": 3, "day": 8, "name": "International Women's Day", "theme": "Women-focused content"},
    {"month": 5, "day": 1, "name": "Labour Day", "theme": "Holiday promos"},
    {"month": 7, "day": 1, "name": "HKSAR Establishment Day", "theme": "HK pride content"},
    {"month": 9, "day": 1, "name": "Mid-Autumn (approx.)", "theme": "Mooncake season / festive"},
    {"month": 10, "day": 1, "name": "National Day / Golden Week", "theme": "Holiday shopping"},
    {"month": 11, "day": 11, "name": "Singles' Day (11.11)", "theme": "Flash sales"},
    {"month": 11, "day": 25, "name": "Black Friday (approx.)", "theme": "Mega sales"},
    {"month": 12, "day": 25, "name": "Christmas Day", "theme": "Christmas promos"},
    {"month": 12, "day": 26, "name": "Boxing Day Sales", "theme": "Post-Christmas sales"},
]

# CNY dates shift yearly; use approximate late-Jan / early-Feb placeholder
_CNY_APPROX = {"month": 1, "day": 29, "name": "Chinese New Year (approx.)", "theme": "CNY campaign / 利是 promos"}


def get_calendar(
    db_path: str | Path,
    year: int,
    month: int,
) -> list[dict[str, Any]]:
    """Return all calendar entries for a given year/month."""
    start = f"{year:04d}-{month:02d}-01"
    if month == 12:
        end = f"{year + 1:04d}-01-01"
    else:
        end = f"{year:04d}-{month + 1:02d}-01"

    with get_db(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM content_calendar WHERE date >= ? AND date < ? ORDER BY date",
            (start, end),
        ).fetchall()
    return [dict(r) for r in rows]


def add_calendar_entry(
    db_path: str | Path,
    entry_date: str,
    theme: str,
    notes: str = "",
    is_hk_event: bool = False,
    event_name: str | None = None,
) -> dict[str, Any]:
    """Insert a new calendar entry and return it."""
    with get_db(db_path) as conn:
        cursor = conn.execute(
            """INSERT INTO content_calendar (date, theme, notes, is_hk_event, event_name)
               VALUES (?, ?, ?, ?, ?)""",
            (entry_date, theme, notes, is_hk_event, event_name),
        )
        entry_id = cursor.lastrowid
        row = conn.execute(
            "SELECT * FROM content_calendar WHERE id = ?", (entry_id,)
        ).fetchone()
    return dict(row)


def seed_hk_events(db_path: str | Path, year: int) -> int:
    """Pre-load known HK seasonal events for *year*.

    Skips duplicates (same date + event_name). Returns count inserted.
    """
    events = HK_EVENTS + [_CNY_APPROX]
    inserted = 0

    with get_db(db_path) as conn:
        for ev in events:
            d = f"{year:04d}-{ev['month']:02d}-{ev['day']:02d}"
            existing = conn.execute(
                "SELECT id FROM content_calendar WHERE date = ? AND event_name = ?",
                (d, ev["name"]),
            ).fetchone()
            if existing:
                continue
            conn.execute(
                """INSERT INTO content_calendar (date, theme, notes, is_hk_event, event_name)
                   VALUES (?, ?, '', 1, ?)""",
                (d, ev["theme"], ev["name"]),
            )
            inserted += 1

    logger.info("Seeded %d HK events for %d", inserted, year)
    return inserted


def get_upcoming_events(
    db_path: str | Path,
    days_ahead: int = 14,
) -> list[dict[str, Any]]:
    """Return calendar entries (especially HK events) in the next *days_ahead* days."""
    today = date.today().isoformat()
    cutoff = (date.today() + timedelta(days=days_ahead)).isoformat()

    with get_db(db_path) as conn:
        rows = conn.execute(
            """SELECT * FROM content_calendar
               WHERE date >= ? AND date <= ?
               ORDER BY date""",
            (today, cutoff),
        ).fetchall()
    return [dict(r) for r in rows]
