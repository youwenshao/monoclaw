"""LLM-powered flashcard generation from document chunks."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import chromadb

from openclaw_shared.database import get_db
from openclaw_shared.llm.base import LLMProvider

SYSTEM_PROMPT = (
    "You are a study assistant that creates flashcards. Given study material, "
    "generate 3-5 question-answer pairs. Return a JSON array where each object "
    'has keys: "question", "answer", "difficulty" (easy/medium/hard). '
    "Focus on key concepts, definitions, and important relationships. "
    "Return ONLY valid JSON, no additional text."
)


async def generate_flashcards(
    document_id: int,
    db_path: str | Path,
    chroma_client: chromadb.ClientAPI,
    llm: LLMProvider,
) -> list[dict[str, Any]]:
    with get_db(db_path) as conn:
        chunks = [dict(r) for r in conn.execute(
            "SELECT text_content, section_title FROM chunks WHERE document_id = ? ORDER BY chunk_index",
            (document_id,),
        ).fetchall()]

    if not chunks:
        return []

    sections: dict[str, list[str]] = {}
    for chunk in chunks:
        key = chunk.get("section_title") or "General"
        sections.setdefault(key, []).append(chunk["text_content"])

    all_flashcards: list[dict] = []

    for section_title, texts in sections.items():
        combined = "\n\n".join(texts)[:3000]
        prompt = f"Section: {section_title}\n\nMaterial:\n{combined}"

        try:
            response = await llm.generate(prompt, system=SYSTEM_PROMPT, max_tokens=1024, temperature=0.3)
            cards = _parse_flashcards(response)
            all_flashcards.extend(cards)
        except Exception:
            continue

    return all_flashcards


def _parse_flashcards(raw: str) -> list[dict]:
    text = raw.strip()
    start = text.find("[")
    end = text.rfind("]") + 1
    if start == -1 or end == 0:
        return []

    try:
        cards = json.loads(text[start:end])
    except json.JSONDecodeError:
        return []

    valid: list[dict] = []
    for card in cards:
        if isinstance(card, dict) and "question" in card and "answer" in card:
            valid.append({
                "question": str(card["question"]),
                "answer": str(card["answer"]),
                "difficulty": card.get("difficulty", "medium"),
            })
    return valid
