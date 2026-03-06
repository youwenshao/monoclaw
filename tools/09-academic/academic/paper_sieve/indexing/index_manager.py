"""Index lifecycle management — orchestrate embedding and ChromaDB storage."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from openclaw_shared.database import get_db

from academic.paper_sieve.indexing.chroma_store import (
    add_chunks,
    delete_paper,
    get_collection,
)
from academic.paper_sieve.indexing.embedder import embed_texts

logger = logging.getLogger("openclaw.academic.paper_sieve.index_manager")


def index_paper(
    db_path: str | Path,
    chroma_path: str | Path,
    paper_id: int,
    chunks: list[dict[str, Any]],
    model_name: str = "paraphrase-multilingual-MiniLM-L12-v2",
) -> dict[str, Any]:
    """Full indexing pipeline for a single paper.

    1. Embed all chunks
    2. Store embeddings in ChromaDB
    3. Record chunk metadata in SQLite
    4. Mark the paper as indexed

    Returns a summary dict with chunk_count, paper_id, and chroma_ids.
    """
    if not chunks:
        return {"paper_id": paper_id, "chunk_count": 0, "chroma_ids": []}

    texts = [c["text"] for c in chunks]
    embeddings = embed_texts(texts, model_name=model_name)

    collection = get_collection(chroma_path)

    delete_paper(collection, paper_id)
    chroma_ids = add_chunks(collection, chunks, embeddings, paper_id)

    with get_db(db_path) as conn:
        conn.execute("DELETE FROM chunks WHERE paper_id = ?", (paper_id,))

        for chunk, chroma_id in zip(chunks, chroma_ids):
            conn.execute(
                """INSERT INTO chunks
                   (paper_id, chunk_index, section_name, text_content, chroma_id, token_count)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    paper_id,
                    chunk["chunk_index"],
                    chunk.get("section_name", ""),
                    chunk["text"],
                    chroma_id,
                    chunk.get("token_count", 0),
                ),
            )

        conn.execute(
            "UPDATE papers SET indexed = TRUE, chunk_count = ? WHERE id = ?",
            (len(chunks), paper_id),
        )

    logger.info("Indexed paper_id=%d: %d chunks", paper_id, len(chunks))
    return {
        "paper_id": paper_id,
        "chunk_count": len(chunks),
        "chroma_ids": chroma_ids,
    }


def reindex_all(
    db_path: str | Path,
    chroma_path: str | Path,
    model_name: str = "paraphrase-multilingual-MiniLM-L12-v2",
) -> dict[str, Any]:
    """Rebuild the entire index from chunks stored in SQLite.

    Drops the existing ChromaDB collection and re-embeds every chunk.
    Returns a summary with total_papers, total_chunks, and any errors.
    """
    results: dict[str, Any] = {
        "total_papers": 0,
        "total_chunks": 0,
        "errors": [],
    }

    chroma_path = Path(chroma_path)
    chroma_path.mkdir(parents=True, exist_ok=True)
    client = __import__("chromadb").PersistentClient(path=str(chroma_path))

    try:
        client.delete_collection("paper_sieve")
    except Exception:
        pass

    collection = get_collection(chroma_path)

    with get_db(db_path) as conn:
        papers = conn.execute(
            "SELECT id, title FROM papers ORDER BY id"
        ).fetchall()

    for paper in papers:
        paper_id = paper["id"]
        results["total_papers"] += 1

        try:
            with get_db(db_path) as conn:
                rows = conn.execute(
                    """SELECT chunk_index, section_name, text_content, token_count
                       FROM chunks WHERE paper_id = ? ORDER BY chunk_index""",
                    (paper_id,),
                ).fetchall()

            if not rows:
                continue

            chunks = [
                {
                    "chunk_index": row["chunk_index"],
                    "section_name": row["section_name"],
                    "text": row["text_content"],
                    "token_count": row["token_count"],
                }
                for row in rows
            ]

            texts = [c["text"] for c in chunks]
            embeddings = embed_texts(texts, model_name=model_name)
            chroma_ids = add_chunks(collection, chunks, embeddings, paper_id)

            with get_db(db_path) as conn:
                for chunk, cid in zip(chunks, chroma_ids):
                    conn.execute(
                        "UPDATE chunks SET chroma_id = ? WHERE paper_id = ? AND chunk_index = ?",
                        (cid, paper_id, chunk["chunk_index"]),
                    )
                conn.execute(
                    "UPDATE papers SET indexed = TRUE WHERE id = ?",
                    (paper_id,),
                )

            results["total_chunks"] += len(chunks)

        except Exception as exc:
            logger.error("Failed to reindex paper_id=%d: %s", paper_id, exc)
            results["errors"].append({"paper_id": paper_id, "error": str(exc)})

    logger.info(
        "Reindex complete: %d papers, %d chunks, %d errors",
        results["total_papers"],
        results["total_chunks"],
        len(results["errors"]),
    )
    return results


def get_index_stats(
    db_path: str | Path,
    chroma_path: str | Path,
) -> dict[str, Any]:
    """Return index statistics from both SQLite and ChromaDB.

    Returns a dict with: total_papers, indexed_papers, total_chunks_db,
    total_chunks_chroma, and collection_metadata.
    """
    stats: dict[str, Any] = {
        "total_papers": 0,
        "indexed_papers": 0,
        "total_chunks_db": 0,
        "total_chunks_chroma": 0,
        "collection_metadata": {},
    }

    with get_db(db_path) as conn:
        row = conn.execute("SELECT COUNT(*) AS cnt FROM papers").fetchone()
        stats["total_papers"] = row["cnt"]

        row = conn.execute(
            "SELECT COUNT(*) AS cnt FROM papers WHERE indexed = TRUE"
        ).fetchone()
        stats["indexed_papers"] = row["cnt"]

        row = conn.execute("SELECT COUNT(*) AS cnt FROM chunks").fetchone()
        stats["total_chunks_db"] = row["cnt"]

    try:
        collection = get_collection(chroma_path)
        stats["total_chunks_chroma"] = collection.count()
        stats["collection_metadata"] = collection.metadata or {}
    except Exception as exc:
        logger.warning("Could not read ChromaDB stats: %s", exc)

    return stats
