"""Socratic discussion engine for post-exam question review."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Union

from openclaw_shared.database import get_db

from student.exam_generator.discussion.context_builder import build_discussion_context


def get_mona_response(
    attempt_id: int,
    question_id: int,
    student_message: str,
    db_path: Union[str, Path],
    llm: Any,
) -> str:
    context = build_discussion_context(attempt_id, question_id, db_path)

    with get_db(db_path) as conn:
        history = conn.execute(
            """SELECT role, message FROM exam_discussions
               WHERE attempt_id = ? AND question_id = ?
               ORDER BY timestamp ASC LIMIT 10""",
            (attempt_id, question_id),
        ).fetchall()

    chat_history = "\n".join(f"{r['role'].upper()}: {r['message']}" for r in history)

    prompt = (
        "You are Mona, a Socratic tutor helping a student review their exam performance.\n"
        "Guide the student to understand their mistakes WITHOUT giving the answer directly.\n"
        "Ask leading questions. Provide hints. Encourage deeper thinking.\n\n"
        f"CONTEXT:\n{context}\n\n"
        f"CONVERSATION SO FAR:\n{chat_history}\n\n"
        f"STUDENT: {student_message}\n\n"
        "MONA:"
    )

    response = llm.generate(prompt)
    return response if isinstance(response, str) else str(response)


def save_message(
    attempt_id: int,
    question_id: int,
    role: str,
    message: str,
    db_path: Union[str, Path],
) -> None:
    with get_db(db_path) as conn:
        conn.execute(
            "INSERT INTO exam_discussions (attempt_id, question_id, role, message) VALUES (?,?,?,?)",
            (attempt_id, question_id, role, message),
        )
