"""Per-question feedback generation and full exam grading orchestration."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Union

from openclaw_shared.database import get_db

HK_GRADE_SCALE = [
    (85, "A+"), (80, "A"), (75, "A-"),
    (70, "B+"), (65, "B"), (60, "B-"),
    (55, "C+"), (50, "C"), (45, "C-"),
    (40, "D"), (0, "F"),
]


def _letter_grade(percentage: float) -> str:
    for threshold, grade in HK_GRADE_SCALE:
        if percentage >= threshold:
            return grade
    return "F"


def generate_feedback(
    question: dict,
    student_answer: str,
    score: float,
    source_chunks: str,
    llm: Any,
) -> str:
    prompt = (
        "Provide concise feedback for a student's exam answer.\n\n"
        f"QUESTION: {question.get('question_text', '')}\n"
        f"CORRECT ANSWER: {question.get('correct_answer', '')}\n"
        f"STUDENT ANSWER: {student_answer}\n"
        f"SCORE: {score}/{question.get('points', 1.0)}\n\n"
        f"REFERENCE MATERIAL:\n{source_chunks[:1500]}\n\n"
        "Give specific, constructive feedback. Cite relevant source material. "
        "If incorrect, explain why and guide toward the right answer. Keep it under 150 words."
    )

    response = llm.generate(prompt)
    return response if isinstance(response, str) else str(response)


def grade_exam(attempt_id: int, db_path: Union[str, Path], llm: Any) -> dict:
    from student.exam_generator.grading.auto_grader import grade_mcq, grade_true_false, grade_multi_select
    from student.exam_generator.grading.llm_grader import grade_free_form
    from student.exam_generator.grading.calculation_grader import grade_calculation

    with get_db(db_path) as conn:
        attempt = conn.execute("SELECT * FROM exam_attempts WHERE id = ?", (attempt_id,)).fetchone()
        if not attempt:
            return {"error": "Attempt not found"}

        exam_id = attempt["exam_id"]
        answers = conn.execute(
            """SELECT aa.*, eq.question_type, eq.correct_answer, eq.rubric,
                      eq.source_chunks, eq.points, eq.topic, eq.difficulty, eq.options
               FROM attempt_answers aa
               JOIN exam_questions eq ON aa.question_id = eq.id
               WHERE aa.attempt_id = ?""",
            (attempt_id,),
        ).fetchall()

    total_score = 0.0
    max_score = 0.0
    topic_scores: dict[str, dict[str, float]] = {}
    difficulty_scores: dict[str, dict[str, float]] = {}
    now = datetime.now().isoformat()

    for row in answers:
        answer = dict(row)
        q_type = answer["question_type"]
        student_ans = answer.get("student_answer", "")
        correct_ans = answer.get("correct_answer", "")
        points = float(answer.get("points", 1.0))
        rubric = answer.get("rubric", "")
        source_chunks = answer.get("source_chunks", "")
        topic = answer.get("topic", "General")
        difficulty = answer.get("difficulty", "medium")

        if q_type == "mcq":
            result = grade_mcq(student_ans, correct_ans)
            result["score"] *= points
            result["max_score"] = points
        elif q_type == "true_false":
            result = grade_true_false(student_ans, correct_ans)
            result["score"] *= points
            result["max_score"] = points
        elif q_type == "multi_select":
            student_list = json.loads(student_ans) if student_ans.startswith("[") else [student_ans]
            correct_list = json.loads(answer.get("options", "[]")) if correct_ans == "" else json.loads(correct_ans) if correct_ans.startswith("[") else [correct_ans]
            result = grade_multi_select(student_list, correct_list)
            result["score"] *= points
            result["max_score"] = points
        elif q_type == "calculation":
            result = grade_calculation(student_ans, correct_ans, llm)
            scale = points / 4.0
            result["score"] *= scale
            result["max_score"] = points
        else:
            result = grade_free_form(student_ans, correct_ans, rubric, source_chunks, llm)
            scale = points / 5.0
            result["score"] *= scale
            result["max_score"] = points

        total_score += result["score"]
        max_score += result["max_score"]

        topic_scores.setdefault(topic, {"score": 0, "max": 0})
        topic_scores[topic]["score"] += result["score"]
        topic_scores[topic]["max"] += result["max_score"]

        difficulty_scores.setdefault(difficulty, {"score": 0, "max": 0})
        difficulty_scores[difficulty]["score"] += result["score"]
        difficulty_scores[difficulty]["max"] += result["max_score"]

        with get_db(db_path) as conn:
            conn.execute(
                """UPDATE attempt_answers
                   SET is_correct = ?, score = ?, max_score = ?, feedback = ?, graded_at = ?
                   WHERE id = ?""",
                (result["is_correct"], result["score"], result["max_score"],
                 result["feedback"], now, answer["id"]),
            )

    percentage = (total_score / max_score * 100) if max_score > 0 else 0
    letter = _letter_grade(percentage)

    topic_breakdown = {
        t: round(v["score"] / v["max"] * 100, 1) if v["max"] > 0 else 0
        for t, v in topic_scores.items()
    }
    diff_breakdown = {
        d: round(v["score"] / v["max"] * 100, 1) if v["max"] > 0 else 0
        for d, v in difficulty_scores.items()
    }

    with get_db(db_path) as conn:
        conn.execute(
            """UPDATE exam_attempts
               SET total_score = ?, max_score = ?, percentage = ?, letter_grade = ?,
                   topic_breakdown = ?, difficulty_breakdown = ?, status = 'graded'
               WHERE id = ?""",
            (round(total_score, 2), round(max_score, 2), round(percentage, 1),
             letter, json.dumps(topic_breakdown), json.dumps(diff_breakdown), attempt_id),
        )

    return {
        "total_score": round(total_score, 2),
        "max_score": round(max_score, 2),
        "percentage": round(percentage, 1),
        "letter_grade": letter,
        "topic_breakdown": topic_breakdown,
        "difficulty_breakdown": diff_breakdown,
    }
