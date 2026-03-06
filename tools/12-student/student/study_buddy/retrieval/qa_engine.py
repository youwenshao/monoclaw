"""RAG-based question-answering engine."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import chromadb

from openclaw_shared.database import get_db
from openclaw_shared.llm.base import LLMProvider

from student.study_buddy.indexing.chroma_store import get_or_create_collection, query_collection
from student.study_buddy.indexing.embedder import embed_texts

SYSTEM_PROMPT = (
    "You are a study assistant. Answer the student's question using ONLY the "
    "provided context excerpts. Cite sources using [Doc X, p.Y] notation. "
    "If the context doesn't contain enough information, say so clearly."
)


async def answer(
    query: str,
    course_id: int | None,
    db_path: str | Path,
    chroma_client: chromadb.ClientAPI,
    llm: LLMProvider,
) -> dict[str, Any]:
    query_embedding = embed_texts([query])[0]

    course_codes = _get_course_codes(db_path, course_id)
    all_chunks: list[dict] = []
    all_documents: list[str] = []
    all_metadatas: list[dict] = []

    for code in course_codes:
        try:
            results = query_collection(chroma_client, code, query_embedding, n_results=8)
        except Exception:
            continue

        if results.get("documents") and results["documents"][0]:
            all_documents.extend(results["documents"][0])
            all_metadatas.extend(results["metadatas"][0])

    context_parts: list[str] = []
    citations: list[dict] = []

    for i, (doc_text, meta) in enumerate(zip(all_documents[:8], all_metadatas[:8])):
        doc_id = meta.get("document_id", "?")
        page = meta.get("page_number", "?")

        doc_title = _get_doc_title(db_path, doc_id)
        context_parts.append(f"[Source {i+1}: {doc_title}, p.{page}]\n{doc_text}")
        citations.append({
            "document_id": doc_id,
            "document_title": doc_title,
            "page_number": page,
            "chunk_text": doc_text[:200],
        })

    if not context_parts:
        return {"answer": "No relevant materials found for this query.", "citations": []}

    context = "\n\n---\n\n".join(context_parts)
    prompt = f"Context:\n{context}\n\nQuestion: {query}"

    answer_text = await llm.generate(prompt, system=SYSTEM_PROMPT, max_tokens=1024)

    return {"answer": answer_text, "citations": citations}


def _get_course_codes(db_path: str | Path, course_id: int | None) -> list[str]:
    with get_db(db_path) as conn:
        if course_id:
            row = conn.execute(
                "SELECT course_code FROM courses WHERE id = ?", (course_id,)
            ).fetchone()
            return [row[0]] if row else []
        rows = conn.execute("SELECT course_code FROM courses").fetchall()
        return [r[0] for r in rows]


def _get_doc_title(db_path: str | Path, doc_id: str) -> str:
    try:
        with get_db(db_path) as conn:
            row = conn.execute(
                "SELECT title, filename FROM documents WHERE id = ?", (int(doc_id),)
            ).fetchone()
            if row:
                return row[0] or row[1]
    except (ValueError, TypeError):
        pass
    return f"Document {doc_id}"
