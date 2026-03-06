"""Parse past exam papers from PDF into structured question format."""

from __future__ import annotations

import json
from typing import Any

import fitz


def parse_past_paper(file_path: str, llm: Any) -> list[dict]:
    doc = fitz.open(file_path)
    full_text = ""
    for page in doc:
        full_text += page.get_text("text") + "\n\n"
    doc.close()

    if not full_text.strip():
        return []

    prompt = (
        "You are an exam paper parser. Extract every question from the following past exam paper text.\n"
        "Return a JSON array where each element has:\n"
        "- question_text: the full question text\n"
        "- question_type: one of mcq, multi_select, short_answer, long_answer, calculation, true_false\n"
        "- options: array of option strings (null if not MCQ)\n"
        "- correct_answer: the correct answer if visible, otherwise empty string\n"
        "- points: point value as number\n"
        "- topic: inferred topic\n\n"
        "Respond with ONLY the JSON array, no other text.\n\n"
        f"EXAM PAPER TEXT:\n{full_text[:8000]}"
    )

    response = llm.generate(prompt)
    text = response if isinstance(response, str) else str(response)

    start = text.find("[")
    end = text.rfind("]") + 1
    if start == -1 or end == 0:
        return []

    try:
        questions = json.loads(text[start:end])
    except json.JSONDecodeError:
        return []

    parsed: list[dict] = []
    for q in questions:
        parsed.append({
            "question_text": q.get("question_text", ""),
            "question_type": q.get("question_type", "short_answer"),
            "options": q.get("options"),
            "correct_answer": q.get("correct_answer", ""),
            "points": float(q.get("points", 1.0)),
            "topic": q.get("topic", ""),
        })

    return parsed
