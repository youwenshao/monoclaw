"""Map ChromaDB chunk IDs back to document and page info."""

from __future__ import annotations

from pathlib import Path

from openclaw_shared.database import get_db


def resolve_citations(chunk_ids: list[str], db_path: str | Path) -> list[dict]:
    citations: list[dict] = []

    for cid in chunk_ids:
        parts = cid.replace("chunk_", "").split("_", 1)
        if len(parts) < 2:
            continue

        try:
            doc_id = int(parts[0])
            chunk_index = int(parts[1])
        except ValueError:
            continue

        with get_db(db_path) as conn:
            doc = conn.execute(
                "SELECT id, title, filename FROM documents WHERE id = ?",
                (doc_id,),
            ).fetchone()
            chunk = conn.execute(
                "SELECT page_number, section_title, text_content FROM chunks WHERE document_id = ? AND chunk_index = ?",
                (doc_id, chunk_index),
            ).fetchone()

        if doc and chunk:
            citations.append({
                "document_id": doc[0],
                "document_title": doc[1] or doc[2],
                "page_number": chunk[0],
                "section_title": chunk[1],
                "excerpt": chunk[2][:200] if chunk[2] else "",
            })

    return citations
