"""Generate plausible MCQ distractors based on common misconceptions."""

from __future__ import annotations

import json
from typing import Any


def generate_distractors(correct_answer: str, context: str, count: int, llm: Any) -> list[str]:
    prompt = (
        f"The correct answer to an exam question is: {correct_answer}\n\n"
        f"Context: {context[:2000]}\n\n"
        f"Generate exactly {count} plausible but incorrect MCQ distractors.\n"
        "Each distractor should be based on a common misconception or partial understanding.\n"
        "Return a JSON array of strings.\n"
        "Respond with ONLY the JSON array."
    )

    response = llm.generate(prompt)
    text = response if isinstance(response, str) else str(response)

    start = text.find("[")
    end = text.rfind("]") + 1
    if start == -1 or end == 0:
        return [f"Incorrect option {i + 1}" for i in range(count)]

    try:
        distractors = json.loads(text[start:end])
    except json.JSONDecodeError:
        return [f"Incorrect option {i + 1}" for i in range(count)]

    return [str(d) for d in distractors[:count]]
