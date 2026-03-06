"""Track problem-solving progress and streaks."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from openclaw_shared.database import get_db


def update_progress(problem: dict, attempt: dict, db_path: str | Path) -> None:
    topic = problem.get("topic", "general")

    with get_db(db_path) as conn:
        row = conn.execute("SELECT * FROM progress WHERE topic = ?", (topic,)).fetchone()

        if row:
            current = dict(row)
            attempted = current["problems_attempted"] + 1
            solved = current["problems_solved"] + (1 if attempt.get("is_correct") else 0)
            avg_time = (
                (current["avg_time_seconds"] or 0) * current["problems_attempted"]
                + (attempt.get("time_spent_seconds") or 0)
            ) / attempted
            avg_hints = (
                (current["avg_hints_used"] or 0) * current["problems_attempted"]
                + (attempt.get("hints_used") or 0)
            ) / attempted
            solve_rate = solved / attempted if attempted else 0

            strength = "weak"
            if solve_rate >= 0.7:
                strength = "strong"
            elif solve_rate >= 0.3:
                strength = "developing"

            conn.execute(
                """UPDATE progress SET
                   problems_attempted = ?, problems_solved = ?,
                   avg_time_seconds = ?, avg_hints_used = ?,
                   solve_rate = ?, strength_level = ?,
                   last_practiced = ?
                   WHERE topic = ?""",
                (attempted, solved, avg_time, avg_hints, solve_rate, strength,
                 datetime.utcnow().isoformat(), topic),
            )
        else:
            is_correct = attempt.get("is_correct", False)
            conn.execute(
                """INSERT INTO progress
                   (topic, problems_attempted, problems_solved, avg_time_seconds,
                    avg_hints_used, solve_rate, strength_level, last_practiced)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (topic, 1, 1 if is_correct else 0,
                 attempt.get("time_spent_seconds", 0),
                 attempt.get("hints_used", 0),
                 1.0 if is_correct else 0.0,
                 "developing" if is_correct else "weak",
                 datetime.utcnow().isoformat()),
            )


def get_topic_progress(db_path: str | Path) -> list[dict]:
    with get_db(db_path) as conn:
        rows = conn.execute("SELECT * FROM progress ORDER BY topic").fetchall()
    return [dict(r) for r in rows]


def get_streak(db_path: str | Path) -> int:
    with get_db(db_path) as conn:
        rows = conn.execute(
            "SELECT DISTINCT DATE(submitted_at) as d FROM attempts ORDER BY d DESC"
        ).fetchall()

    if not rows:
        return 0

    from datetime import date, timedelta
    dates = [date.fromisoformat(r["d"]) for r in rows if r["d"]]
    if not dates:
        return 0

    streak = 1
    for i in range(1, len(dates)):
        if dates[i - 1] - dates[i] == timedelta(days=1):
            streak += 1
        else:
            break

    return streak
