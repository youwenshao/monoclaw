"""Track overall and per-course exam performance."""

from __future__ import annotations

from pathlib import Path
from typing import Union

from openclaw_shared.database import get_db


def get_performance_summary(db_path: Union[str, Path]) -> dict:
    with get_db(db_path) as conn:
        total_attempts = conn.execute(
            "SELECT COUNT(*) FROM exam_attempts WHERE status = 'graded'"
        ).fetchone()[0]

        if total_attempts == 0:
            return {
                "total_attempts": 0,
                "avg_score": 0,
                "avg_percentage": 0,
                "best_grade": "N/A",
                "total_time_hours": 0,
            }

        agg = conn.execute(
            """SELECT AVG(percentage) as avg_pct, AVG(total_score) as avg_score,
                      MAX(percentage) as best_pct, SUM(time_spent_seconds) as total_time
               FROM exam_attempts WHERE status = 'graded'"""
        ).fetchone()

        best_grade_row = conn.execute(
            "SELECT letter_grade FROM exam_attempts WHERE status = 'graded' ORDER BY percentage DESC LIMIT 1"
        ).fetchone()

    return {
        "total_attempts": total_attempts,
        "avg_score": round(agg["avg_score"] or 0, 2),
        "avg_percentage": round(agg["avg_pct"] or 0, 1),
        "best_grade": best_grade_row["letter_grade"] if best_grade_row else "N/A",
        "total_time_hours": round((agg["total_time"] or 0) / 3600, 1),
    }


def get_course_performance(course_id: int, db_path: Union[str, Path]) -> dict:
    with get_db(db_path) as conn:
        rows = conn.execute(
            """SELECT ea.* FROM exam_attempts ea
               JOIN exams e ON ea.exam_id = e.id
               WHERE e.course_id = ? AND ea.status = 'graded'
               ORDER BY ea.started_at DESC""",
            (course_id,),
        ).fetchall()

    if not rows:
        return {"course_id": course_id, "attempts": 0, "avg_percentage": 0, "trend": []}

    attempts = [dict(r) for r in rows]
    avg_pct = sum(a["percentage"] for a in attempts) / len(attempts)

    return {
        "course_id": course_id,
        "attempts": len(attempts),
        "avg_percentage": round(avg_pct, 1),
        "best_percentage": max(a["percentage"] for a in attempts),
        "latest_grade": attempts[0].get("letter_grade", "N/A"),
        "trend": [{"date": a.get("started_at", "")[:10], "percentage": a["percentage"]} for a in attempts],
    }
