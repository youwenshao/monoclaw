"""ChromaDB vector store operations for PaperSieve."""

from __future__ import annotations

import logging
import uuid
from pathlib import Path
from typing import Any

import chromadb

logger = logging.getLogger("openclaw.academic.paper_sieve.chroma_store")


def get_collection(
    db_path: str | Path,
    collection_name: str = "paper_sieve",
) -> chromadb.Collection:
    """Return a ChromaDB collection, creating it if it doesn't exist.

    Uses persistent storage at *db_path*.
    """
    path = Path(db_path)
    path.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(path))
    collection = client.get_or_create_collection(
        name=collection_name,
        metadata={"hnsw:space": "cosine"},
    )
    logger.info(
        "ChromaDB collection '%s' at %s (count=%d)",
        collection_name,
        path,
        collection.count(),
    )
    return collection


def add_chunks(
    collection: chromadb.Collection,
    chunks: list[dict[str, Any]],
    embeddings: list[list[float]],
    paper_id: int,
) -> list[str]:
    """Add paper chunks with embeddings and metadata to the collection.

    Returns the list of generated chroma IDs for each chunk.
    """
    if not chunks or not embeddings:
        return []

    if len(chunks) != len(embeddings):
        raise ValueError(
            f"Chunk count ({len(chunks)}) != embedding count ({len(embeddings)})"
        )

    ids: list[str] = []
    documents: list[str] = []
    metadatas: list[dict[str, Any]] = []

    for chunk in chunks:
        chroma_id = f"paper_{paper_id}_chunk_{chunk['chunk_index']}_{uuid.uuid4().hex[:8]}"
        ids.append(chroma_id)
        documents.append(chunk["text"])
        metadatas.append({
            "paper_id": paper_id,
            "chunk_index": chunk["chunk_index"],
            "section_name": chunk.get("section_name", ""),
            "token_count": chunk.get("token_count", 0),
        })

    collection.add(
        ids=ids,
        embeddings=embeddings,
        documents=documents,
        metadatas=metadatas,
    )
    logger.info("Added %d chunks for paper_id=%d to ChromaDB", len(ids), paper_id)
    return ids


def search(
    collection: chromadb.Collection,
    query_embedding: list[float],
    n_results: int = 10,
    filters: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Search the collection by embedding similarity.

    Returns a list of result dicts with: id, text, metadata, distance.
    """
    where = None
    if filters:
        where_clauses = []
        for key, value in filters.items():
            where_clauses.append({key: {"$eq": value}})
        if len(where_clauses) == 1:
            where = where_clauses[0]
        elif where_clauses:
            where = {"$and": where_clauses}

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=n_results,
        where=where,
        include=["documents", "metadatas", "distances"],
    )

    output: list[dict[str, Any]] = []
    if not results["ids"] or not results["ids"][0]:
        return output

    for i, chroma_id in enumerate(results["ids"][0]):
        output.append({
            "id": chroma_id,
            "text": results["documents"][0][i] if results["documents"] else "",
            "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
            "distance": results["distances"][0][i] if results["distances"] else None,
        })

    return output


def delete_paper(collection: chromadb.Collection, paper_id: int) -> int:
    """Remove all chunks for a given paper_id from the collection.

    Returns the number of chunks deleted.
    """
    existing = collection.get(
        where={"paper_id": {"$eq": paper_id}},
        include=[],
    )
    ids_to_delete = existing["ids"] if existing["ids"] else []

    if ids_to_delete:
        collection.delete(ids=ids_to_delete)
        logger.info("Deleted %d chunks for paper_id=%d", len(ids_to_delete), paper_id)

    return len(ids_to_delete)
