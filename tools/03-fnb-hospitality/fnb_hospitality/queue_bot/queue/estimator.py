"""Wait time estimator using exponential moving average of turnover times.

Segmented by party size bracket (1-2, 3-4, 5-6, 7+) and time slot.
Falls back to static estimates during the first week of operation.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from openclaw_shared.database import get_db

STATIC_FALLBACK: dict[str, int] = {
    "1-2": 20,
    "3-4": 30,
    "5-6": 40,
    "7+": 55,
}

EMA_ALPHA = 0.3
MIN_SAMPLES = 3

BRACKET_RANGES: dict[str, tuple[int, int]] = {
    "1-2": (1, 2),
    "3-4": (3, 4),
    "5-6": (5, 6),
    "7+": (7, 99),
}


def _bracket(party_size: int) -> str:
    if party_size <= 2:
        return "1-2"
    if party_size <= 4:
        return "3-4"
    if party_size <= 6:
        return "5-6"
    return "7+"


def _time_slot() -> str:
    hour = datetime.now().hour
    if hour < 15:
        return "lunch"
    return "dinner"


def _ema(values: list[float], alpha: float = EMA_ALPHA) -> float:
    """Compute exponential moving average (newest values weighted more)."""
    if not values:
        return 0.0
    result = values[0]
    for v in values[1:]:
        result = alpha * v + (1 - alpha) * result
    return result


def estimate_wait(db_path: str | Path, party_size: int) -> int:
    """Estimate wait time in minutes for a given party size.

    Uses EMA of recent turnover durations for the matching bracket and
    time slot. The per-group turnover is scaled by queue position and a
    parallelism factor (multiple tables can be served simultaneously).

    Returns the static fallback when fewer than MIN_SAMPLES records exist.
    """
    bracket = _bracket(party_size)
    slot = _time_slot()
    lo, hi = BRACKET_RANGES[bracket]

    with get_db(db_path) as conn:
        rows = conn.execute(
            """SELECT duration_minutes FROM table_turnover
               WHERE party_size BETWEEN ? AND ?
                 AND time_slot = ?
               ORDER BY date DESC, seated_at DESC
               LIMIT 50""",
            (lo, hi, slot),
        ).fetchall()

    durations = [r[0] for r in rows if r[0] is not None]

    if len(durations) < MIN_SAMPLES:
        base = STATIC_FALLBACK[bracket]
    else:
        base = _ema(durations)

    with get_db(db_path) as conn:
        ahead = conn.execute(
            "SELECT COUNT(*) FROM queue_entries WHERE status IN ('waiting', 'notified')",
        ).fetchone()[0]

    if ahead == 0:
        return max(int(base * 0.3), 5)

    tables_factor = 2.5
    wait = int(base * ahead / tables_factor)
    return max(wait, 5)
