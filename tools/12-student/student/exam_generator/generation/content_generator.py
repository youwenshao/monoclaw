"""Generate exam questions from indexed course materials via ChromaDB."""

from __future__ import annotations

import json
from typing import Any

from student.exam_generator.generation.bloom_classifier import distribute_questions
from student.exam_generator.generation.subject_adapter import get_subject_prompt


def generate_from_index(
    course_id: int,
    scope_config: dict,
    question_count: int,
    question_types: list[str],
    difficulty_dist: dict[str, float],
    chroma_client: Any,
    db_path: Any,
    llm: Any,
) -> list[dict]:
    collection_name = f"course_{course_id}"
    try:
        collection = chroma_client.get_collection(collection_name)
    except Exception:
        return []

    topics = scope_config.get("topics", [])
    query_text = " ".join(topics) if topics else "exam review key concepts"

    results = collection.query(query_texts=[query_text], n_results=min(20, question_count * 3))
    documents = results.get("documents", [[]])[0]
    if not documents:
        return []

    context = "\n---\n".join(documents[:15])
    dist = distribute_questions(question_count, difficulty_dist)
    subject_prompt = get_subject_prompt(scope_config.get("course_code", ""))

    type_str = ", ".join(question_types)
    diff_str = ", ".join(f"{k}: {v}" for k, v in dist.items())

    prompt = (
        f"{subject_prompt}\n\n"
        f"Generate exactly {question_count} exam questions based on the following course material.\n"
        f"Question types to use: {type_str}\n"
        f"Difficulty distribution: {diff_str}\n\n"
        "Return a JSON array where each element has:\n"
        "- question_text, question_type, options (array or null), correct_answer\n"
        "- rubric, difficulty (easy/medium/hard), topic, bloom_level, points\n\n"
        "Respond with ONLY the JSON array.\n\n"
        f"COURSE MATERIAL:\n{context[:6000]}"
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

    for q in questions:
        q.setdefault("source_chunks", documents[:3])

    return questions
