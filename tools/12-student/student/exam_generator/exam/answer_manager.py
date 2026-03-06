"""Manage student answers for exam attempts."""

from __future__ import annotations

from pathlib import Path
from typing import Union

from openclaw_shared.database import get_db


def save_answer(
    attempt_id: int,
    question_id: int,
    student_answer: str,
    flagged: bool,
    db_path: Union[str, Path],
) -> None:
    with get_db(db_path) as conn:
        existing = conn.execute(
            "SELECT id FROM attempt_answers WHERE attempt_id = ? AND question_id = ?",
            (attempt_id, question_id),
        ).fetchone()

        if existing:
            conn.execute(
                "UPDATE attempt_answers SET student_answer = ?, flagged_for_review = ? WHERE id = ?",
                (student_answer, flagged, existing["id"]),
            )
        else:
            conn.execute(
                """INSERT INTO attempt_answers (attempt_id, question_id, student_answer, flagged_for_review)
                   VALUES (?,?,?,?)""",
                (attempt_id, question_id, student_answer, flagged),
            )


def get_answers(attempt_id: int, db_path: Union[str, Path]) -> list[dict]:
    with get_db(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM attempt_answers WHERE attempt_id = ? ORDER BY question_id",
            (attempt_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def get_answer_for_question(
    attempt_id: int, question_id: int, db_path: Union[str, Path]
) -> dict | None:
    with get_db(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM attempt_answers WHERE attempt_id = ? AND question_id = ?",
            (attempt_id, question_id),
        ).fetchone()
    return dict(row) if row else None
