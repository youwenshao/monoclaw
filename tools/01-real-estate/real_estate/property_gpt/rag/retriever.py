"""Vector + SQL hybrid search for Hong Kong buildings."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from openclaw_shared.database import get_db
from openclaw_shared.llm.base import LLMProvider

logger = logging.getLogger(__name__)

COLLECTION_NAME = "hk_buildings"


async def search_buildings(
    llm: LLMProvider,
    db_path: str | Path,
    query: str,
    *,
    district: str | None = None,
    min_price: int | None = None,
    max_price: int | None = None,
    limit: int = 10,
) -> list[dict[str, Any]]:
    """Search buildings using ChromaDB vector similarity, falling back to SQL."""
    try:
        return await _vector_search(
            llm, db_path, query,
            district=district, min_price=min_price,
            max_price=max_price, limit=limit,
        )
    except Exception:
        logger.warning("ChromaDB unavailable, falling back to SQL search", exc_info=True)
        return _sql_search(
            db_path, query,
            district=district, min_price=min_price,
            max_price=max_price, limit=limit,
        )


async def _vector_search(
    llm: LLMProvider,
    db_path: str | Path,
    query: str,
    *,
    district: str | None = None,
    min_price: int | None = None,
    max_price: int | None = None,
    limit: int = 10,
) -> list[dict[str, Any]]:
    import chromadb

    chroma_dir = str(Path(db_path).parent / "chroma")
    client = chromadb.PersistentClient(path=chroma_dir)
    collection = client.get_collection(name=COLLECTION_NAME)

    query_embedding = (await llm.embed([query]))[0]

    where_clauses: list[dict] = []
    if district:
        where_clauses.append({"district": {"$eq": district}})
    if min_price is not None:
        where_clauses.append({"price_psf": {"$gte": min_price}})
    if max_price is not None:
        where_clauses.append({"price_psf": {"$lte": max_price}})

    where: dict | None = None
    if len(where_clauses) == 1:
        where = where_clauses[0]
    elif len(where_clauses) > 1:
        where = {"$and": where_clauses}

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=limit,
        where=where,
        include=["documents", "metadatas", "distances"],
    )

    buildings: list[dict[str, Any]] = []
    if results["ids"] and results["ids"][0]:
        for idx, doc_id in enumerate(results["ids"][0]):
            meta = results["metadatas"][0][idx] if results["metadatas"] else {}
            distance = results["distances"][0][idx] if results["distances"] else None
            buildings.append({
                "id": int(doc_id),
                "text": results["documents"][0][idx] if results["documents"] else "",
                "score": round(1 - distance, 4) if distance is not None else None,
                **meta,
            })

    return buildings


def _sql_search(
    db_path: str | Path,
    query: str,
    *,
    district: str | None = None,
    min_price: int | None = None,
    max_price: int | None = None,
    limit: int = 10,
) -> list[dict[str, Any]]:
    """Keyword-based SQL fallback using LIKE."""
    conditions = ["(name_en LIKE ? OR name_zh LIKE ? OR district LIKE ? OR address_en LIKE ?)"]
    params: list[Any] = [f"%{query}%"] * 4

    if district:
        conditions.append("district = ?")
        params.append(district)
    if min_price is not None:
        conditions.append("price_psf >= ?")
        params.append(min_price)
    if max_price is not None:
        conditions.append("price_psf <= ?")
        params.append(max_price)

    sql = f"SELECT * FROM buildings WHERE {' AND '.join(conditions)} LIMIT ?"
    params.append(limit)

    with get_db(db_path) as conn:
        rows = conn.execute(sql, params).fetchall()

    return [dict(r) for r in rows]
