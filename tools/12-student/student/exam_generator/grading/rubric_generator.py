"""Generate grading rubrics from source material."""

from __future__ import annotations

import json
from typing import Any


def generate_rubric(
    question_text: str,
    correct_answer: str,
    source_chunks: str,
    max_score: float,
    llm: Any,
) -> str:
    prompt = (
        "Create a detailed grading rubric for the following exam question.\n\n"
        f"QUESTION: {question_text}\n\n"
        f"MODEL ANSWER: {correct_answer}\n\n"
        f"REFERENCE MATERIAL:\n{source_chunks[:2000]}\n\n"
        f"MAXIMUM SCORE: {max_score}\n\n"
        "The rubric should:\n"
        "- Break down marks by key points the student must cover\n"
        "- Specify what earns full, partial, and zero marks\n"
        "- Note common errors to watch for\n\n"
        "Return the rubric as plain text."
    )

    response = llm.generate(prompt)
    return response if isinstance(response, str) else str(response)
