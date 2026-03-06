"""Key concept and relationship extraction from academic text."""

from __future__ import annotations

import json
import logging
from typing import Any

from openclaw_shared.database import get_db

logger = logging.getLogger("openclaw.academic.paper_sieve.concept_extractor")


def extract_concepts(text: str, llm: Any) -> list[dict[str, Any]]:
    """Extract key concepts and their relationships from *text* via LLM.

    Returns a list of dicts: {concept, type, related_to: list[str]}.
    """
    prompt = (
        "You are an academic knowledge extraction system. "
        "From the following text, extract the key concepts and their relationships.\n\n"
        "For each concept provide:\n"
        "- concept: the concept name (short, canonical form)\n"
        "- type: one of 'theory', 'method', 'finding', 'dataset', 'metric', 'entity', 'other'\n"
        "- related_to: list of other concept names from this extraction that are related\n\n"
        "Return ONLY a JSON array. Example:\n"
        '[{"concept": "transformer", "type": "method", "related_to": ["attention mechanism"]}]\n\n'
        f"Text:\n{text[:4000]}\n\n"
        "JSON:"
    )

    raw = llm.generate(prompt).strip()

    try:
        concepts = json.loads(raw)
    except json.JSONDecodeError:
        start = raw.find("[")
        end = raw.rfind("]") + 1
        if start != -1 and end > start:
            try:
                concepts = json.loads(raw[start:end])
            except json.JSONDecodeError:
                logger.error("Failed to parse concept extraction output")
                return []
        else:
            return []

    if not isinstance(concepts, list):
        return []

    validated: list[dict[str, Any]] = []
    for item in concepts:
        if not isinstance(item, dict) or "concept" not in item:
            continue
        validated.append({
            "concept": str(item["concept"]),
            "type": str(item.get("type", "other")),
            "related_to": [str(r) for r in item.get("related_to", []) if isinstance(r, str)],
        })

    return validated


def extract_paper_concepts(
    db_path: str,
    paper_id: int,
    llm: Any,
) -> list[dict[str, Any]]:
    """Extract concepts from all chunks of a specific paper.

    Merges concept lists across chunks, deduplicating by concept name
    and unioning their relationships.
    """
    with get_db(db_path) as conn:
        rows = conn.execute(
            "SELECT text_content FROM chunks WHERE paper_id = ? ORDER BY chunk_index",
            (paper_id,),
        ).fetchall()

    if not rows:
        logger.warning("No chunks found for paper id=%d", paper_id)
        return []

    merged: dict[str, dict[str, Any]] = {}

    for row in rows:
        chunk_concepts = extract_concepts(row["text_content"], llm)
        for c in chunk_concepts:
            name = c["concept"].lower()
            if name in merged:
                existing_related = set(merged[name]["related_to"])
                existing_related.update(c["related_to"])
                merged[name]["related_to"] = list(existing_related)
            else:
                merged[name] = {
                    "concept": c["concept"],
                    "type": c["type"],
                    "related_to": list(c["related_to"]),
                    "paper_id": paper_id,
                }

    return list(merged.values())
