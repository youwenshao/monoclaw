"""Application analytics: funnel, response rate, volume trends."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from openclaw_shared.database import get_db

ACTIVE_STAGES = {"applied", "phone_screen", "assessment", "interview", "final_round", "offer", "accepted"}


def get_funnel_data(db_path: str | Path) -> dict:
    with get_db(db_path) as conn:
        rows = conn.execute(
            "SELECT stage, COUNT(*) as cnt FROM applications GROUP BY stage"
        ).fetchall()
    counts = {r["stage"]: r["cnt"] for r in rows}

    stages_order = [
        "saved", "applied", "phone_screen", "assessment",
        "interview", "final_round", "offer", "accepted",
    ]
    return {
        "stages": stages_order,
        "counts": [counts.get(s, 0) for s in stages_order],
    }


def get_response_rate(db_path: str | Path) -> float:
    with get_db(db_path) as conn:
        total = conn.execute(
            "SELECT COUNT(*) FROM applications WHERE stage != 'saved'"
        ).fetchone()[0]
        responded = conn.execute(
            "SELECT COUNT(*) FROM applications WHERE stage IN "
            "('phone_screen','assessment','interview','final_round','offer','accepted','rejected')"
        ).fetchone()[0]

    if total == 0:
        return 0.0
    return round(responded / total, 3)


def get_weekly_volume(db_path: str | Path) -> list[dict]:
    with get_db(db_path) as conn:
        rows = conn.execute(
            """SELECT strftime('%Y-W%W', applied_date) as week,
                      COUNT(*) as count
               FROM applications
               WHERE applied_date IS NOT NULL
               GROUP BY week
               ORDER BY week DESC
               LIMIT 12"""
        ).fetchall()
    return [{"week": r["week"], "count": r["count"]} for r in reversed(rows)]


def get_time_to_response(db_path: str | Path) -> dict:
    with get_db(db_path) as conn:
        rows = conn.execute(
            """SELECT julianday(response_date) - julianday(applied_date) as days
               FROM applications
               WHERE applied_date IS NOT NULL AND response_date IS NOT NULL"""
        ).fetchall()

    if not rows:
        return {"avg_days": None, "median_days": None, "sample_size": 0}

    days_list = sorted(r["days"] for r in rows if r["days"] is not None and r["days"] >= 0)
    if not days_list:
        return {"avg_days": None, "median_days": None, "sample_size": 0}

    avg = sum(days_list) / len(days_list)
    mid = len(days_list) // 2
    median = (
        days_list[mid]
        if len(days_list) % 2 == 1
        else (days_list[mid - 1] + days_list[mid]) / 2
    )

    return {
        "avg_days": round(avg, 1),
        "median_days": round(median, 1),
        "sample_size": len(days_list),
    }


def create_snapshot(db_path: str | Path) -> None:
    with get_db(db_path) as conn:
        counts = {}
        for row in conn.execute("SELECT stage, COUNT(*) as cnt FROM applications GROUP BY stage").fetchall():
            counts[row["stage"]] = row["cnt"]

        total_applied = sum(counts.get(s, 0) for s in ACTIVE_STAGES)
        total_saved = counts.get("saved", 0)
        total_interviews = sum(counts.get(s, 0) for s in ("interview", "final_round"))
        total_offers = sum(counts.get(s, 0) for s in ("offer", "accepted"))

        response_rate = get_response_rate(db_path)
        ttr = get_time_to_response(db_path)

        conn.execute(
            """INSERT INTO analytics_snapshots
               (snapshot_date, total_saved, total_applied, total_interviews,
                total_offers, response_rate, avg_time_to_response_days)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                date.today().isoformat(),
                total_saved,
                total_applied,
                total_interviews,
                total_offers,
                response_rate,
                ttr["avg_days"],
            ),
        )
