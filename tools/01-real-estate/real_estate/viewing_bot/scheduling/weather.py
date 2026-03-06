"""Hong Kong Observatory weather warning integration."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import httpx

from openclaw_shared.database import get_db
from openclaw_shared.mona_events import emit_event

logger = logging.getLogger("openclaw.viewing_bot.weather")

HKO_WARNING_URL = "https://data.weather.gov.hk/weatherAPI/opendata/weather.php"
HKO_WARNING_PARAMS = {"dataType": "warningInfo", "lang": "en"}

UNSAFE_SIGNALS = {
    "TC8NE", "TC8SE", "TC8NW", "TC8SW", "TC9", "TC10",
    "WRAINB",
}

CAUTION_SIGNALS = {
    "TC3",
    "WRAINA",
    "WFIRER",
}


async def get_weather_warnings() -> list[dict[str, Any]]:
    """Fetch active weather warnings from the HK Observatory API."""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(HKO_WARNING_URL, params=HKO_WARNING_PARAMS)
            resp.raise_for_status()
            data = resp.json()

        warnings: list[dict[str, Any]] = []
        for code, details in data.get("details", {}).items():
            warnings.append({
                "code": code,
                "name": details.get("warningStatementContent", code),
                "type": details.get("type", ""),
                "action_code": details.get("actionCode", ""),
                "contents": details.get("contents", []),
                "is_unsafe": code in UNSAFE_SIGNALS,
                "is_caution": code in CAUTION_SIGNALS,
            })

        if not data.get("details"):
            for item in data.get("warningMessage", []):
                if isinstance(item, str):
                    warnings.append({
                        "code": "INFO",
                        "name": item,
                        "type": "info",
                        "action_code": "",
                        "contents": [],
                        "is_unsafe": False,
                        "is_caution": False,
                    })

        return warnings
    except httpx.HTTPError as exc:
        logger.error("HKO API request failed: %s", exc)
        return []
    except Exception as exc:
        logger.error("Unexpected error fetching weather: %s", exc)
        return []


def is_viewing_unsafe(warnings: list[dict[str, Any]]) -> bool:
    """Return True if any active warning indicates unsafe viewing conditions.

    Unsafe = Typhoon Signal 8+ or Black Rainstorm.
    """
    return any(w.get("is_unsafe") for w in warnings)


async def auto_cancel_unsafe_viewings(
    db_path: str | Path,
    warnings: list[dict[str, Any]],
    mona_db_path: str | Path | None = None,
) -> list[int]:
    """Cancel today's pending/confirmed viewings when unsafe weather is active.

    Returns list of cancelled viewing IDs.
    """
    if not is_viewing_unsafe(warnings):
        return []

    signal_names = [w["code"] for w in warnings if w.get("is_unsafe")]
    reason = f"Auto-cancelled: unsafe weather ({', '.join(signal_names)})"

    cancelled_ids: list[int] = []
    with get_db(db_path) as conn:
        rows = conn.execute(
            """SELECT id FROM viewings
               WHERE status IN ('pending', 'confirmed')
                 AND DATE(COALESCE(confirmed_datetime, proposed_datetime)) = DATE('now')""",
        ).fetchall()

        for row in rows:
            vid = row["id"]
            conn.execute(
                "UPDATE viewings SET status = 'cancelled', notes = COALESCE(notes || '\\n', '') || ? WHERE id = ?",
                (reason, vid),
            )
            cancelled_ids.append(vid)

    if cancelled_ids:
        logger.warning("Auto-cancelled %d viewings due to %s", len(cancelled_ids), signal_names)
        if mona_db_path:
            emit_event(
                mona_db_path,
                event_type="alert",
                tool_name="viewing-bot",
                summary=f"Weather alert: {len(cancelled_ids)} viewings auto-cancelled",
                details=reason,
                requires_human_action=True,
            )

    return cancelled_ids
