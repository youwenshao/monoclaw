"""Classify questions into Bloom's taxonomy levels and distribute by difficulty."""

from __future__ import annotations

import re

BLOOM_KEYWORDS: dict[str, list[str]] = {
    "remember": ["define", "list", "name", "recall", "identify", "state", "match", "label"],
    "understand": ["explain", "describe", "summarize", "interpret", "paraphrase", "classify", "discuss"],
    "apply": ["apply", "calculate", "solve", "demonstrate", "use", "implement", "execute", "compute"],
    "analyze": ["analyze", "compare", "contrast", "differentiate", "examine", "distinguish", "categorize"],
    "evaluate": ["evaluate", "justify", "argue", "critique", "assess", "judge", "defend", "recommend"],
    "create": ["design", "create", "construct", "develop", "propose", "formulate", "synthesize", "plan"],
}


def classify_bloom_level(question_text: str) -> str:
    text_lower = question_text.lower()

    best_level = "understand"
    best_score = 0

    for level, keywords in BLOOM_KEYWORDS.items():
        score = sum(1 for kw in keywords if re.search(rf"\b{kw}\b", text_lower))
        if score > best_score:
            best_score = score
            best_level = level

    return best_level


def distribute_questions(count: int, distribution: dict[str, float]) -> dict[str, int]:
    if not distribution:
        distribution = {"easy": 0.3, "medium": 0.5, "hard": 0.2}

    total_weight = sum(distribution.values())
    if total_weight == 0:
        return {"medium": count}

    result: dict[str, int] = {}
    assigned = 0
    items = sorted(distribution.items(), key=lambda x: x[1], reverse=True)

    for i, (level, weight) in enumerate(items):
        if i == len(items) - 1:
            result[level] = count - assigned
        else:
            n = round(count * weight / total_weight)
            result[level] = n
            assigned += n

    return {k: v for k, v in result.items() if v > 0}
