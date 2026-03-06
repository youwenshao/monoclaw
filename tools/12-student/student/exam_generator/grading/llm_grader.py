"""LLM-based grading for free-form (short/long answer) questions."""

from __future__ import annotations

import json
from typing import Any


def grade_free_form(
    student_answer: str,
    correct_answer: str,
    rubric: str,
    source_chunks: str,
    llm: Any,
) -> dict:
    if not student_answer.strip():
        return {"score": 0.0, "max_score": 5.0, "feedback": "No answer provided.", "is_correct": False}

    prompt = (
        "You are a university exam grader. Grade the following student answer.\n\n"
        f"QUESTION RUBRIC:\n{rubric}\n\n"
        f"MODEL ANSWER:\n{correct_answer}\n\n"
        f"REFERENCE MATERIAL:\n{source_chunks[:2000]}\n\n"
        f"STUDENT ANSWER:\n{student_answer}\n\n"
        "Respond with ONLY a JSON object:\n"
        '{"score": <float 0-5>, "max_score": 5.0, "feedback": "<detailed feedback>", "is_correct": <bool>}'
    )

    response = llm.generate(prompt)
    text = response if isinstance(response, str) else str(response)

    start = text.find("{")
    end = text.rfind("}") + 1
    if start == -1 or end == 0:
        return {"score": 0.0, "max_score": 5.0, "feedback": "Unable to grade automatically.", "is_correct": False}

    try:
        result = json.loads(text[start:end])
        return {
            "score": float(result.get("score", 0)),
            "max_score": float(result.get("max_score", 5.0)),
            "feedback": result.get("feedback", ""),
            "is_correct": bool(result.get("is_correct", False)),
        }
    except (json.JSONDecodeError, ValueError):
        return {"score": 0.0, "max_score": 5.0, "feedback": "Unable to grade automatically.", "is_correct": False}
