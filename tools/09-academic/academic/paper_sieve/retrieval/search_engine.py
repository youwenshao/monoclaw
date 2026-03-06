"""Semantic search with citation tracking over indexed academic papers."""

from __future__ import annotations

import logging
from typing import Any

from openclaw_shared.database import get_db

from academic.paper_sieve.indexing.chroma_store import get_collection, search
from academic.paper_sieve.indexing.embedder import embed_query

logger = logging.getLogger("openclaw.academic.paper_sieve.search_engine")


def semantic_search(
    db_path: str,
    chroma_path: str,
    query: str,
    n_results: int = 10,
    filters: dict[str, Any] | None = None,
    model_name: str = "paraphrase-multilingual-MiniLM-L12-v2",
) -> list[dict[str, Any]]:
    """Embed *query*, search ChromaDB, and enrich results with paper metadata.

    Returns a list of dicts with keys: paper_id, paper_title, authors, year,
    section_name, text_content, page_number, score.
    """
    query_embedding = embed_query(query, model_name=model_name)
    collection = get_collection(chroma_path)
    raw_results = search(collection, query_embedding, n_results=n_results, filters=filters)

    if not raw_results:
        return []

    results: list[dict[str, Any]] = []
    for hit in raw_results:
        meta = hit.get("metadata", {})
        results.append({
            "paper_id": meta.get("paper_id"),
            "chroma_id": hit["id"],
            "section_name": meta.get("section_name", ""),
            "text_content": hit.get("text", ""),
            "chunk_index": meta.get("chunk_index"),
            "score": 1.0 - (hit.get("distance") or 0.0),
        })

    return _enrich_with_metadata(db_path, results)


def _enrich_with_metadata(
    db_path: str,
    results: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Join chunk search results with paper metadata from SQLite."""
    paper_ids = list({r["paper_id"] for r in results if r.get("paper_id") is not None})
    if not paper_ids:
        return results

    placeholders = ",".join("?" for _ in paper_ids)
    with get_db(db_path) as conn:
        rows = conn.execute(
            f"SELECT id, title, authors, year FROM papers WHERE id IN ({placeholders})",  # noqa: S608
            paper_ids,
        ).fetchall()
        paper_map = {row["id"]: dict(row) for row in rows}

        valid_results = [r for r in results if r.get("paper_id") is not None]
        if valid_results:
            pair_clauses = " OR ".join(
                "(paper_id = ? AND chunk_index = ?)" for _ in valid_results
            )
            pair_params: list[Any] = []
            for r in valid_results:
                pair_params.extend([r["paper_id"], r["chunk_index"]])
            chunk_rows = conn.execute(
                f"SELECT paper_id, chunk_index, page_number FROM chunks WHERE {pair_clauses}",  # noqa: S608
                pair_params,
            ).fetchall()
            page_map = {(row["paper_id"], row["chunk_index"]): row["page_number"] for row in chunk_rows}
        else:
            page_map = {}

    enriched: list[dict[str, Any]] = []
    for r in results:
        paper = paper_map.get(r.get("paper_id"), {})
        enriched.append({
            "paper_id": r.get("paper_id"),
            "paper_title": paper.get("title", ""),
            "authors": paper.get("authors", ""),
            "year": paper.get("year"),
            "section_name": r.get("section_name", ""),
            "text_content": r.get("text_content", ""),
            "page_number": page_map.get((r.get("paper_id"), r.get("chunk_index"))),
            "score": r.get("score", 0.0),
        })

    return enriched
