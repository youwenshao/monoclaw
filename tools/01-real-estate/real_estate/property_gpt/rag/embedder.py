"""Ingest building data into ChromaDB for vector search."""

from __future__ import annotations

import json
import logging
from pathlib import Path

import chromadb

from openclaw_shared.database import get_db
from openclaw_shared.llm.base import LLMProvider

logger = logging.getLogger(__name__)

COLLECTION_NAME = "hk_buildings"
BATCH_SIZE = 64


def _building_text(row: dict) -> str:
    """Serialise a building row into a search-friendly text chunk."""
    parts = [
        row.get("name_en", ""),
        row.get("name_zh", ""),
        row.get("district", ""),
        row.get("address_en", ""),
        row.get("address_zh", ""),
    ]
    if row.get("developer"):
        parts.append(f"Developer: {row['developer']}")
    if row.get("year_built"):
        parts.append(f"Built {row['year_built']}")
    if row.get("total_units"):
        parts.append(f"{row['total_units']} units")
    if row.get("mtr_walk_minutes") is not None:
        parts.append(f"MTR walk {row['mtr_walk_minutes']} min")
    if row.get("school_net"):
        parts.append(f"School net {row['school_net']}")
    return " | ".join(p for p in parts if p)


async def ingest_buildings(llm: LLMProvider, db_path: str | Path) -> int:
    """Read all buildings from SQLite and upsert into ChromaDB.

    Returns the number of documents ingested.
    """
    chroma_dir = str(Path(db_path).parent / "chroma")
    client = chromadb.PersistentClient(path=chroma_dir)
    collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )

    with get_db(db_path) as conn:
        rows = conn.execute("SELECT * FROM buildings").fetchall()

    if not rows:
        logger.warning("No buildings found in database — nothing to ingest")
        return 0

    buildings = [dict(r) for r in rows]
    ingested = 0

    for i in range(0, len(buildings), BATCH_SIZE):
        batch = buildings[i : i + BATCH_SIZE]
        texts = [_building_text(b) for b in batch]
        ids = [str(b["id"]) for b in batch]
        metadatas = [
            {
                "name_en": b.get("name_en", ""),
                "name_zh": b.get("name_zh", ""),
                "district": b.get("district", ""),
                "year_built": b.get("year_built", 0),
                "price_psf": b.get("price_psf", 0),
            }
            for b in batch
        ]

        embeddings = await llm.embed(texts)
        collection.upsert(
            ids=ids,
            documents=texts,
            embeddings=embeddings,
            metadatas=metadatas,
        )
        ingested += len(batch)
        logger.info("Ingested buildings %d–%d of %d", i + 1, i + len(batch), len(buildings))

    logger.info("Ingestion complete: %d buildings", ingested)
    return ingested
