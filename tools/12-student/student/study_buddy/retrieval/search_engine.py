"""Semantic search across course materials."""

from __future__ import annotations

from pathlib import Path

import chromadb

from openclaw_shared.database import get_db

from student.study_buddy.indexing.chroma_store import query_collection
from student.study_buddy.indexing.embedder import embed_texts


def search(
    query: str,
    course_id: int | None,
    db_path: str | Path,
    chroma_client: chromadb.ClientAPI,
    n_results: int = 10,
) -> list[dict]:
    query_embedding = embed_texts([query])[0]

    course_codes = _get_search_scopes(db_path, course_id)
    results_list: list[dict] = []

    for code in course_codes:
        try:
            results = query_collection(chroma_client, code, query_embedding, n_results=n_results)
        except Exception:
            continue

        if not results.get("documents") or not results["documents"][0]:
            continue

        for doc_text, meta, distance in zip(
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0],
        ):
            doc_title = _resolve_title(db_path, meta.get("document_id", ""))
            results_list.append({
                "chunk_text": doc_text,
                "document_title": doc_title,
                "page_number": meta.get("page_number", 0),
                "score": round(1.0 - distance, 4) if distance <= 1.0 else round(1.0 / (1.0 + distance), 4),
            })

    results_list.sort(key=lambda r: r["score"], reverse=True)
    return results_list[:n_results]


def _get_search_scopes(db_path: str | Path, course_id: int | None) -> list[str]:
    with get_db(db_path) as conn:
        if course_id:
            row = conn.execute(
                "SELECT course_code FROM courses WHERE id = ?", (course_id,)
            ).fetchone()
            return [row[0]] if row else []
        return [r[0] for r in conn.execute("SELECT course_code FROM courses").fetchall()]


def _resolve_title(db_path: str | Path, doc_id: str) -> str:
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
