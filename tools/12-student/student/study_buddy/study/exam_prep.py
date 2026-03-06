"""Past paper analysis for exam preparation."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import chromadb

from openclaw_shared.database import get_db

from student.study_buddy.indexing.chroma_store import query_collection
from student.study_buddy.indexing.embedder import embed_texts
from student.study_buddy.ingestion.chunker import chunk_text
from student.study_buddy.ingestion.pdf_parser import parse_pdf


def analyze_past_paper(
    file_path: str,
    course_id: int,
    db_path: str | Path,
    chroma_client: chromadb.ClientAPI,
) -> dict[str, Any]:
    pages = parse_pdf(file_path)
    questions = _extract_questions(pages)

    with get_db(db_path) as conn:
        row = conn.execute(
            "SELECT course_code FROM courses WHERE id = ?", (course_id,)
        ).fetchone()
    course_code = row[0] if row else ""

    topic_map: dict[str, dict] = {}

    for q in questions:
        embedding = embed_texts([q["text"]])[0]
        try:
            results = query_collection(chroma_client, course_code, embedding, n_results=3)
        except Exception:
            continue

        topic = q.get("topic", "General")
        if topic not in topic_map:
            topic_map[topic] = {"name": topic, "question_count": 0, "relevant_chunks": []}

        topic_map[topic]["question_count"] += 1

        if results.get("documents") and results["documents"][0]:
            for doc_text, meta in zip(results["documents"][0], results["metadatas"][0]):
                topic_map[topic]["relevant_chunks"].append({
                    "text": doc_text[:200],
                    "document_id": meta.get("document_id", ""),
                    "page_number": meta.get("page_number", 0),
                })

    return {"topics": list(topic_map.values())}


def _extract_questions(pages: list[dict]) -> list[dict]:
    questions: list[dict] = []
    current_topic = "General"

    for page in pages:
        lines = page["text"].split("\n")
        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue

            if stripped.startswith("Section") or stripped.startswith("Part"):
                current_topic = stripped

            if any(stripped.startswith(p) for p in ("Q", "q", "Question")) or (
                len(stripped) > 2 and stripped[0].isdigit() and stripped[1] in ".)"
            ):
                questions.append({
                    "text": stripped,
                    "topic": current_topic,
                    "page": page.get("page_number", 0),
                })

    return questions
