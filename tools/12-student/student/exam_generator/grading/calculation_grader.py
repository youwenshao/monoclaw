"""Grading for calculation/numerical questions with partial credit for working."""

from __future__ import annotations

import json
from typing import Any


def grade_calculation(student_answer: str, correct_answer: str, llm: Any) -> dict:
    if not student_answer.strip():
        return {"score": 0.0, "max_score": 4.0, "feedback": "No answer provided.", "is_correct": False}

    prompt = (
        "You are grading a calculation question. Check BOTH the final answer and working/steps.\n\n"
        f"CORRECT ANSWER: {correct_answer}\n\n"
        f"STUDENT ANSWER:\n{student_answer}\n\n"
        "Award partial credit:\n"
        "- 4/4: Correct final answer with valid working\n"
        "- 3/4: Correct final answer, incomplete working\n"
        "- 2/4: Wrong final answer, but correct method/approach\n"
        "- 1/4: Some relevant working shown\n"
        "- 0/4: No relevant content\n\n"
        "Respond with ONLY a JSON object:\n"
        '{"score": <float 0-4>, "max_score": 4.0, "feedback": "<explain scoring>", "is_correct": <bool>}'
    )

    response = llm.generate(prompt)
    text = response if isinstance(response, str) else str(response)

    start = text.find("{")
    end = text.rfind("}") + 1
    if start == -1 or end == 0:
        return {"score": 0.0, "max_score": 4.0, "feedback": "Unable to grade automatically.", "is_correct": False}

    try:
        result = json.loads(text[start:end])
        return {
            "score": float(result.get("score", 0)),
            "max_score": 4.0,
            "feedback": result.get("feedback", ""),
            "is_correct": bool(result.get("is_correct", False)),
        }
    except (json.JSONDecodeError, ValueError):
        return {"score": 0.0, "max_score": 4.0, "feedback": "Unable to grade automatically.", "is_correct": False}
