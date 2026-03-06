"""Identify weak topics from exam performance data."""

from __future__ import annotations

from pathlib import Path
from typing import Union

from openclaw_shared.database import get_db

STRENGTH_THRESHOLDS = {"strong": 75, "developing": 50}


def analyze_weaknesses(db_path: Union[str, Path]) -> list[dict]:
    with get_db(db_path) as conn:
        rows = conn.execute(
            """SELECT eq.topic,
                      COUNT(*) as attempts,
                      SUM(CASE WHEN aa.is_correct THEN 1 ELSE 0 END) as correct,
                      AVG(aa.score) as avg_score,
                      AVG(aa.max_score) as avg_max
               FROM attempt_answers aa
               JOIN exam_questions eq ON aa.question_id = eq.id
               WHERE aa.graded_at IS NOT NULL AND eq.topic IS NOT NULL AND eq.topic != ''
               GROUP BY eq.topic
               ORDER BY AVG(aa.score * 1.0 / CASE WHEN aa.max_score > 0 THEN aa.max_score ELSE 1 END) ASC"""
        ).fetchall()

    topics: list[dict] = []
    for r in rows:
        row = dict(r)
        attempts = row["attempts"]
        correct = row["correct"] or 0
        correct_rate = round(correct / attempts * 100, 1) if attempts > 0 else 0
        avg_score = round(row["avg_score"] or 0, 2)

        if correct_rate >= STRENGTH_THRESHOLDS["strong"]:
            strength = "strong"
        elif correct_rate >= STRENGTH_THRESHOLDS["developing"]:
            strength = "developing"
        else:
            strength = "weak"

        topics.append({
            "topic": row["topic"],
            "attempts": attempts,
            "correct_rate": correct_rate,
            "avg_score": avg_score,
            "strength_level": strength,
        })

    return topics
