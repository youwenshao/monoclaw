"""Assemble questions into a structured exam with sections and ordering."""

from __future__ import annotations


SECTION_MAP = {
    "mcq": "A",
    "multi_select": "A",
    "true_false": "A",
    "short_answer": "B",
    "calculation": "B",
    "long_answer": "C",
}

SECTION_ORDER = {"A": 0, "B": 1, "C": 2}


def build_exam(questions: list[dict], exam_config: dict) -> dict:
    for q in questions:
        q_type = q.get("question_type", "short_answer")
        q.setdefault("section", SECTION_MAP.get(q_type, "B"))

    questions.sort(key=lambda q: (
        SECTION_ORDER.get(q.get("section", "B"), 1),
        {"easy": 0, "medium": 1, "hard": 2}.get(q.get("difficulty", "medium"), 1),
    ))

    total_points = 0.0
    for i, q in enumerate(questions):
        q["question_index"] = i + 1
        total_points += float(q.get("points", 1.0))

    sections: dict[str, list[dict]] = {}
    for q in questions:
        sec = q.get("section", "B")
        sections.setdefault(sec, []).append(q)

    return {
        "questions": questions,
        "sections": sections,
        "total_points": total_points,
        "question_count": len(questions),
        "time_limit_minutes": exam_config.get("time_limit_minutes", 60),
    }
