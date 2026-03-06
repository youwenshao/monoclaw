"""LLM-powered document summarization at configurable detail levels."""

from __future__ import annotations

from pathlib import Path

import chromadb

from openclaw_shared.database import get_db
from openclaw_shared.llm.base import LLMProvider

DETAIL_PROMPTS = {
    "brief": (
        "Summarize the following study material in 3-5 concise bullet points. "
        "Focus only on the most important takeaways."
    ),
    "detailed": (
        "Provide a thorough summary of the following study material. "
        "Cover all major sections, key concepts, and important details. "
        "Use headings and bullet points for clarity."
    ),
    "key_concepts": (
        "Extract and explain the key concepts from the following study material. "
        "For each concept, provide a brief definition and its significance. "
        "Format as a list of concept definitions."
    ),
}


async def generate_summary(
    document_id: int,
    detail_level: str,
    db_path: str | Path,
    chroma_client: chromadb.ClientAPI,
    llm: LLMProvider,
) -> str:
    with get_db(db_path) as conn:
        doc = conn.execute(
            "SELECT title, filename FROM documents WHERE id = ?", (document_id,)
        ).fetchone()
        chunks = [dict(r) for r in conn.execute(
            "SELECT text_content, section_title FROM chunks WHERE document_id = ? ORDER BY chunk_index",
            (document_id,),
        ).fetchall()]

    if not chunks:
        return "No content found for this document."

    doc_title = doc[0] or doc[1] if doc else "Unknown Document"
    combined = "\n\n".join(c["text_content"] for c in chunks)[:6000]

    system = DETAIL_PROMPTS.get(detail_level, DETAIL_PROMPTS["detailed"])
    prompt = f"Document: {doc_title}\n\n{combined}"

    max_tokens = 512 if detail_level == "brief" else 1024
    return await llm.generate(prompt, system=system, max_tokens=max_tokens, temperature=0.3)
