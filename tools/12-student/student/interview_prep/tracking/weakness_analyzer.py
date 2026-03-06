"""Analyze weak topics based on solve rate."""

from __future__ import annotations

from pathlib import Path

from openclaw_shared.database import get_db


def analyze_weaknesses(db_path: str | Path) -> list[dict]:
    with get_db(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM progress WHERE solve_rate < 0.3 OR strength_level = 'weak' ORDER BY solve_rate ASC"
        ).fetchall()

    weaknesses = []
    for row in rows:
        r = dict(row)
        weaknesses.append({
            "topic": r["topic"],
            "solve_rate": r.get("solve_rate", 0),
            "problems_attempted": r.get("problems_attempted", 0),
            "problems_solved": r.get("problems_solved", 0),
            "avg_time_seconds": r.get("avg_time_seconds", 0),
            "recommendation": _get_recommendation(r),
        })

    return weaknesses


def _get_recommendation(progress: dict) -> str:
    solve_rate = progress.get("solve_rate", 0)
    attempted = progress.get("problems_attempted", 0)

    if attempted < 3:
        return "Practice more problems in this topic to build familiarity"
    if solve_rate == 0:
        return "Review fundamentals and start with easy problems"
    if solve_rate < 0.15:
        return "Focus on understanding the core patterns before attempting harder problems"
    return "Keep practicing — you're close to breaking through"
