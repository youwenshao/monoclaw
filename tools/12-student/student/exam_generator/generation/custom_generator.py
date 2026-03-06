"""Generate exam questions from custom topic/requirements specification."""

from __future__ import annotations

import json
from typing import Any


def generate_custom(
    topic: str,
    requirements: str,
    question_count: int,
    question_types: list[str],
    llm: Any,
) -> list[dict]:
    type_str = ", ".join(question_types) if question_types else "mcq, short_answer, long_answer"

    prompt = (
        f"Generate exactly {question_count} exam questions on the topic: {topic}\n\n"
        f"Requirements: {requirements}\n"
        f"Question types to use: {type_str}\n\n"
        "Return a JSON array where each element has:\n"
        "- question_text: string\n"
        "- question_type: one of mcq, multi_select, short_answer, long_answer, calculation, true_false\n"
        "- options: array of 4 strings for MCQ/multi_select, null otherwise\n"
        "- correct_answer: string\n"
        "- rubric: grading criteria string\n"
        "- difficulty: easy, medium, or hard\n"
        "- topic: specific sub-topic string\n"
        "- bloom_level: one of remember, understand, apply, analyze, evaluate, create\n"
        "- points: number (MCQ=1, short=3, long=5, calculation=4)\n\n"
        "Respond with ONLY the JSON array, no other text."
    )

    response = llm.generate(prompt)
    text = response if isinstance(response, str) else str(response)

    start = text.find("[")
    end = text.rfind("]") + 1
    if start == -1 or end == 0:
        return _fallback_questions(topic, question_count)

    try:
        questions = json.loads(text[start:end])
    except json.JSONDecodeError:
        return _fallback_questions(topic, question_count)

    validated: list[dict] = []
    for q in questions:
        validated.append({
            "question_text": q.get("question_text", ""),
            "question_type": q.get("question_type", "short_answer"),
            "options": q.get("options"),
            "correct_answer": q.get("correct_answer", ""),
            "rubric": q.get("rubric", ""),
            "difficulty": q.get("difficulty", "medium"),
            "topic": q.get("topic", topic),
            "bloom_level": q.get("bloom_level", "understand"),
            "points": float(q.get("points", 1.0)),
            "source_chunks": [],
        })

    return validated


def _fallback_questions(topic: str, count: int) -> list[dict]:
    return [
        {
            "question_text": f"Explain the key concepts of {topic} (Question {i + 1}).",
            "question_type": "short_answer",
            "options": None,
            "correct_answer": "",
            "rubric": "Award marks for clarity, accuracy, and completeness.",
            "difficulty": "medium",
            "topic": topic,
            "bloom_level": "understand",
            "points": 3.0,
            "source_chunks": [],
        }
        for i in range(count)
    ]
