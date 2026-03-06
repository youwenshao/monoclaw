"""Provide progressive hints for coding problems."""

from __future__ import annotations

import json


async def get_hint(problem: dict, hint_level: int, llm) -> str:
    stored_hints = problem.get("hints", [])
    if isinstance(stored_hints, str):
        try:
            stored_hints = json.loads(stored_hints)
        except (json.JSONDecodeError, TypeError):
            stored_hints = []

    if stored_hints and 1 <= hint_level <= len(stored_hints):
        return stored_hints[hint_level - 1]

    level_descriptions = {
        1: "Give a high-level strategy hint without revealing the algorithm",
        2: "Suggest the specific algorithm or data structure to use",
        3: "Provide implementation guidance with pseudocode",
    }
    level_desc = level_descriptions.get(hint_level, level_descriptions[1])

    prompt = (
        f"Problem: {problem.get('title', '')}\n"
        f"Description: {problem.get('description', '')}\n\n"
        f"Provide a level {hint_level} hint. {level_desc}. "
        f"Be concise (2-3 sentences). Do not give the full solution."
    )

    response = await llm.generate(prompt)
    return response if isinstance(response, str) else response.get("text", "No hint available")
