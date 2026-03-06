"""Generate follow-up practice questions targeting weak topics."""

from __future__ import annotations

import json
from typing import Any


def generate_followup_questions(weak_topics: list[str], llm: Any) -> list[str]:
    if not weak_topics:
        return []

    topics_str = ", ".join(weak_topics)
    prompt = (
        "A student is weak in the following topics and needs extra practice:\n"
        f"Topics: {topics_str}\n\n"
        "Generate 3-5 follow-up practice questions that specifically target these weak areas.\n"
        "Questions should be at a level that helps reinforce understanding.\n"
        "Return a JSON array of question strings.\n"
        "Respond with ONLY the JSON array."
    )

    response = llm.generate(prompt)
    text = response if isinstance(response, str) else str(response)

    start = text.find("[")
    end = text.rfind("]") + 1
    if start == -1 or end == 0:
        return [f"Explain the key concepts of {t} and provide an example." for t in weak_topics[:3]]

    try:
        questions = json.loads(text[start:end])
        return [str(q) for q in questions]
    except json.JSONDecodeError:
        return [f"Explain the key concepts of {t} and provide an example." for t in weak_topics[:3]]
