"""Exam session lifecycle: start, state tracking, submission."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Union

from openclaw_shared.database import get_db


def start_exam(exam_id: int, db_path: Union[str, Path]) -> int:
    now = datetime.now().isoformat()
    with get_db(db_path) as conn:
        cursor = conn.execute(
            "INSERT INTO exam_attempts (exam_id, started_at, status) VALUES (?,?,?)",
            (exam_id, now, "in_progress"),
        )
        return cursor.lastrowid  # type: ignore[return-value]


def get_exam_state(attempt_id: int, db_path: Union[str, Path]) -> dict:
    with get_db(db_path) as conn:
        attempt = conn.execute(
            "SELECT * FROM exam_attempts WHERE id = ?", (attempt_id,)
        ).fetchone()
        if not attempt:
            return {}

        attempt_data = dict(attempt)
        exam_id = attempt_data["exam_id"]

        total_questions = conn.execute(
            "SELECT COUNT(*) FROM exam_questions WHERE exam_id = ?", (exam_id,)
        ).fetchone()[0]

        answered = conn.execute(
            "SELECT COUNT(*) FROM attempt_answers WHERE attempt_id = ?", (attempt_id,)
        ).fetchone()[0]

        flagged = conn.execute(
            "SELECT COUNT(*) FROM attempt_answers WHERE attempt_id = ? AND flagged_for_review = 1",
            (attempt_id,),
        ).fetchone()[0]

    return {
        **attempt_data,
        "total_questions": total_questions,
        "answered": answered,
        "unanswered": total_questions - answered,
        "flagged": flagged,
    }


def submit_exam(attempt_id: int, db_path: Union[str, Path]) -> dict:
    now = datetime.now()
    with get_db(db_path) as conn:
        attempt = conn.execute(
            "SELECT * FROM exam_attempts WHERE id = ?", (attempt_id,)
        ).fetchone()
        if not attempt:
            return {"error": "Attempt not found"}

        started = datetime.fromisoformat(attempt["started_at"])
        time_spent = int((now - started).total_seconds())

        conn.execute(
            "UPDATE exam_attempts SET submitted_at = ?, time_spent_seconds = ?, status = 'submitted' WHERE id = ?",
            (now.isoformat(), time_spent, attempt_id),
        )

    return {"submitted_at": now.isoformat(), "time_spent_seconds": time_spent, "status": "submitted"}
