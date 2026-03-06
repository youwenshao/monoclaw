"""Build context for exam discussion from question, answer, and grading data."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Union

from openclaw_shared.database import get_db

TOKEN_BUDGET = 4000
CHARS_PER_TOKEN = 4


def build_discussion_context(
    attempt_id: int, question_id: int, db_path: Union[str, Path]
) -> str:
    char_budget = TOKEN_BUDGET * CHARS_PER_TOKEN

    with get_db(db_path) as conn:
        question = conn.execute(
            "SELECT * FROM exam_questions WHERE id = ?", (question_id,)
        ).fetchone()
        answer = conn.execute(
            "SELECT * FROM attempt_answers WHERE attempt_id = ? AND question_id = ?",
            (attempt_id, question_id),
        ).fetchone()

    if not question:
        return "No question data available."

    q = dict(question)
    parts: list[str] = []

    parts.append(f"QUESTION ({q.get('question_type', 'unknown')}, {q.get('difficulty', 'medium')}):")
    parts.append(q.get("question_text", ""))

    if q.get("options"):
        try:
            opts = json.loads(q["options"])
            parts.append("OPTIONS: " + " | ".join(str(o) for o in opts))
        except json.JSONDecodeError:
            pass

    parts.append(f"\nCORRECT ANSWER: {q.get('correct_answer', 'N/A')}")

    if q.get("rubric"):
        parts.append(f"\nRUBRIC: {q['rubric']}")

    if answer:
        a = dict(answer)
        parts.append(f"\nSTUDENT ANSWER: {a.get('student_answer', 'No answer')}")
        parts.append(f"SCORE: {a.get('score', 0)}/{a.get('max_score', 0)}")
        if a.get("feedback"):
            parts.append(f"GRADING FEEDBACK: {a['feedback']}")

    if q.get("source_chunks"):
        try:
            chunks = json.loads(q["source_chunks"])
            if chunks:
                parts.append("\nREFERENCE MATERIAL:")
                for chunk in chunks[:3]:
                    parts.append(str(chunk)[:500])
        except json.JSONDecodeError:
            pass

    context = "\n".join(parts)
    return context[:char_budget]
