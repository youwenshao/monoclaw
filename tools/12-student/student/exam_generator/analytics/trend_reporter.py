"""Generate grade trends and improvement summaries."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Union

from openclaw_shared.database import get_db


def get_grade_trend(course_id: int, db_path: Union[str, Path]) -> list[dict]:
    with get_db(db_path) as conn:
        rows = conn.execute(
            """SELECT ea.started_at, ea.percentage, ea.letter_grade, e.title
               FROM exam_attempts ea
               JOIN exams e ON ea.exam_id = e.id
               WHERE e.course_id = ? AND ea.status = 'graded'
               ORDER BY ea.started_at ASC""",
            (course_id,),
        ).fetchall()

    return [
        {
            "date": r["started_at"][:10] if r["started_at"] else "",
            "percentage": r["percentage"],
            "letter_grade": r["letter_grade"],
            "exam_title": r["title"],
        }
        for r in rows
    ]


def get_improvement_summary(db_path: Union[str, Path], llm: Any) -> str:
    with get_db(db_path) as conn:
        attempts = conn.execute(
            """SELECT ea.percentage, ea.letter_grade, ea.topic_breakdown,
                      ea.started_at, e.title
               FROM exam_attempts ea
               JOIN exams e ON ea.exam_id = e.id
               WHERE ea.status = 'graded'
               ORDER BY ea.started_at DESC LIMIT 10"""
        ).fetchall()

    if not attempts:
        return "No exam data available yet. Take some practice exams to see your progress."

    summaries = []
    for a in attempts:
        topics = json.loads(a["topic_breakdown"]) if a["topic_breakdown"] else {}
        topic_str = ", ".join(f"{t}: {s}%" for t, s in topics.items()) if topics else "N/A"
        summaries.append(f"- {a['title']} ({a['started_at'][:10]}): {a['percentage']}% ({a['letter_grade']}) — Topics: {topic_str}")

    data_text = "\n".join(summaries)

    prompt = (
        "Based on the following exam performance data, write a brief (3-4 sentence) "
        "progress summary for a student. Highlight improvements, persistent weak areas, "
        "and one actionable suggestion.\n\n"
        f"EXAM HISTORY (newest first):\n{data_text}\n\n"
        "Write the summary in second person (you/your)."
    )

    response = llm.generate(prompt)
    return response if isinstance(response, str) else str(response)
