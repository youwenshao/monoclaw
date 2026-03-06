"""Queue analytics: wait times, walkout rates, peak lengths, bottlenecks."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

from openclaw_shared.database import get_db

BRACKETS: dict[str, tuple[int, int]] = {
    "1-2": (1, 2),
    "3-4": (3, 4),
    "5-6": (5, 6),
    "7+": (7, 99),
}


def average_wait_times(db_path: str | Path, days: int = 7) -> dict[str, dict]:
    """Average wait times by party size bracket for the last N days."""
    since = (date.today() - timedelta(days=days)).isoformat()
    result: dict[str, dict] = {}

    with get_db(db_path) as conn:
        for label, (lo, hi) in BRACKETS.items():
            row = conn.execute(
                """SELECT AVG(actual_wait_minutes), COUNT(*)
                   FROM queue_entries
                   WHERE status = 'seated'
                     AND party_size BETWEEN ? AND ?
                     AND DATE(joined_at) >= ?""",
                (lo, hi, since),
            ).fetchone()
            result[label] = {
                "avg_minutes": round(row[0], 1) if row[0] else 0,
                "count": row[1],
            }

    return result


def walkout_rates(db_path: str | Path, days: int = 7) -> dict:
    """Walkout rate for the last N days."""
    since = (date.today() - timedelta(days=days)).isoformat()

    with get_db(db_path) as conn:
        total = conn.execute(
            "SELECT COUNT(*) FROM queue_entries WHERE DATE(joined_at) >= ?",
            (since,),
        ).fetchone()[0]
        walkouts = conn.execute(
            "SELECT COUNT(*) FROM queue_entries WHERE status = 'left' AND DATE(joined_at) >= ?",
            (since,),
        ).fetchone()[0]

    rate = round(walkouts / total * 100, 1) if total > 0 else 0
    return {"total": total, "walkouts": walkouts, "rate_percent": rate}


def peak_queue_lengths(db_path: str | Path, days: int = 7) -> list[dict]:
    """Peak queue length by hour for the last N days."""
    since = (date.today() - timedelta(days=days)).isoformat()

    with get_db(db_path) as conn:
        rows = conn.execute(
            """SELECT hour, MAX(max_queue_length) AS peak,
                      AVG(avg_wait_minutes) AS avg_wait
               FROM queue_analytics
               WHERE date >= ?
               GROUP BY hour
               ORDER BY hour""",
            (since,),
        ).fetchall()

    if rows:
        return [
            {"hour": r[0], "peak_length": r[1],
             "avg_wait": round(r[2], 1) if r[2] else 0}
            for r in rows
        ]

    with get_db(db_path) as conn:
        rows = conn.execute(
            """SELECT CAST(strftime('%H', joined_at) AS INTEGER) AS hour,
                      COUNT(*) AS joined
               FROM queue_entries
               WHERE DATE(joined_at) >= ?
               GROUP BY hour
               ORDER BY hour""",
            (since,),
        ).fetchall()

    return [{"hour": r[0], "peak_length": r[1], "avg_wait": 0} for r in rows]


def party_size_distribution(db_path: str | Path, days: int = 7) -> dict:
    """Party size distribution and bottleneck analysis."""
    since = (date.today() - timedelta(days=days)).isoformat()
    result: dict[str, dict] = {}

    with get_db(db_path) as conn:
        for label, (lo, hi) in BRACKETS.items():
            row = conn.execute(
                """SELECT COUNT(*) AS total,
                          SUM(CASE WHEN status = 'seated' THEN 1 ELSE 0 END) AS seated,
                          SUM(CASE WHEN status = 'left' THEN 1 ELSE 0 END) AS walkouts,
                          AVG(actual_wait_minutes) AS avg_wait
                   FROM queue_entries
                   WHERE party_size BETWEEN ? AND ?
                     AND DATE(joined_at) >= ?""",
                (lo, hi, since),
            ).fetchone()
            total = row[0] or 0
            walkouts = row[2] or 0
            result[label] = {
                "total": total,
                "seated": row[1] or 0,
                "walkouts": walkouts,
                "walkout_rate": round(walkouts / total * 100, 1) if total > 0 else 0,
                "avg_wait": round(row[3], 1) if row[3] else 0,
            }

    candidates = [
        (label, data) for label, data in result.items() if data["total"] >= 3
    ]
    bottleneck = max(candidates, key=lambda x: x[1]["walkout_rate"], default=None)

    return {
        "brackets": result,
        "bottleneck": bottleneck[0] if bottleneck else None,
    }


def daily_summary(db_path: str | Path, target_date: date | None = None) -> dict:
    """Generate a daily queue summary."""
    d = (target_date or date.today()).isoformat()

    with get_db(db_path) as conn:
        total = conn.execute(
            "SELECT COUNT(*) FROM queue_entries WHERE DATE(joined_at) = ?",
            (d,),
        ).fetchone()[0]
        seated = conn.execute(
            "SELECT COUNT(*) FROM queue_entries WHERE DATE(joined_at) = ? AND status = 'seated'",
            (d,),
        ).fetchone()[0]
        walkouts = conn.execute(
            "SELECT COUNT(*) FROM queue_entries WHERE DATE(joined_at) = ? AND status = 'left'",
            (d,),
        ).fetchone()[0]
        avg_wait_row = conn.execute(
            "SELECT AVG(actual_wait_minutes) FROM queue_entries "
            "WHERE DATE(joined_at) = ? AND status = 'seated'",
            (d,),
        ).fetchone()
        max_wait_row = conn.execute(
            "SELECT MAX(actual_wait_minutes) FROM queue_entries "
            "WHERE DATE(joined_at) = ? AND status = 'seated'",
            (d,),
        ).fetchone()

    return {
        "date": d,
        "total_joined": total,
        "total_seated": seated,
        "total_walkouts": walkouts,
        "walkout_rate": round(walkouts / total * 100, 1) if total > 0 else 0,
        "avg_wait_minutes": round(avg_wait_row[0], 1) if avg_wait_row[0] else 0,
        "max_wait_minutes": max_wait_row[0] or 0,
    }
