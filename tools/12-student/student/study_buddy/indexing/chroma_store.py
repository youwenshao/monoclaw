"""ChromaDB persistent vector store management."""

from __future__ import annotations

from typing import Any

import chromadb


def get_chroma_client(persist_dir: str) -> chromadb.ClientAPI:
    return chromadb.PersistentClient(path=persist_dir)


def get_or_create_collection(client: chromadb.ClientAPI, course_code: str) -> Any:
    safe_name = course_code.replace(" ", "_").replace("/", "_").lower()
    return client.get_or_create_collection(name=f"course_{safe_name}")


def add_chunks(
    client: chromadb.ClientAPI,
    course_code: str,
    chunks: list[dict],
    embeddings: list[list[float]],
) -> None:
    collection = get_or_create_collection(client, course_code)
    ids = [f"chunk_{c.get('document_id', 0)}_{c['chunk_index']}" for c in chunks]
    documents = [c["text"] for c in chunks]
    metadatas = [
        {
            "document_id": str(c.get("document_id", "")),
            "page_number": c.get("page_number", 0),
            "section_title": c.get("section_title", ""),
            "chunk_index": c["chunk_index"],
        }
        for c in chunks
    ]

    collection.upsert(
        ids=ids,
        embeddings=embeddings,
        documents=documents,
        metadatas=metadatas,
    )


def query_collection(
    client: chromadb.ClientAPI,
    course_code: str,
    query_embedding: list[float],
    n_results: int = 8,
) -> dict:
    collection = get_or_create_collection(client, course_code)
    return collection.query(
        query_embeddings=[query_embedding],
        n_results=n_results,
        include=["documents", "metadatas", "distances"],
    )


def delete_document_chunks(
    client: chromadb.ClientAPI,
    course_code: str,
    document_id: int,
) -> None:
    collection = get_or_create_collection(client, course_code)
    collection.delete(where={"document_id": str(document_id)})
