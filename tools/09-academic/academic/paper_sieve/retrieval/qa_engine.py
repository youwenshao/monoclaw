"""RAG question-answering over indexed academic papers."""

from __future__ import annotations

import json
import logging
from typing import Any

from openclaw_shared.database import get_db

from academic.paper_sieve.retrieval.search_engine import semantic_search

logger = logging.getLogger("openclaw.academic.paper_sieve.qa_engine")


def answer_question(
    db_path: str,
    chroma_path: str,
    question: str,
    llm: Any,
    n_chunks: int = 5,
    model_name: str = "paraphrase-multilingual-MiniLM-L12-v2",
) -> dict[str, Any]:
    """Full RAG pipeline: search -> build prompt -> LLM answer.

    Returns a dict with keys: answer, sources, confidence.
    """
    chunks = semantic_search(
        db_path, chroma_path, question, n_results=n_chunks, model_name=model_name,
    )

    if not chunks:
        return {
            "answer": "No relevant sources found in the indexed papers.",
            "sources": [],
            "confidence": 0.0,
        }

    prompt = _build_qa_prompt(question, chunks)
    raw_answer = llm.generate(prompt)

    sources = [
        {
            "paper_title": c["paper_title"],
            "authors": c["authors"],
            "year": c["year"],
            "page_number": c["page_number"],
            "text_snippet": c["text_content"][:300],
        }
        for c in chunks
    ]

    avg_score = sum(c.get("score", 0.0) for c in chunks) / len(chunks)
    confidence = round(min(avg_score, 1.0), 3)

    save_query(db_path, question, raw_answer, chunks, confidence)

    return {
        "answer": raw_answer,
        "sources": sources,
        "confidence": confidence,
    }


def _build_qa_prompt(question: str, context_chunks: list[dict[str, Any]]) -> str:
    """Build a prompt instructing the LLM to answer using sources and cite as [Author, Year, p.XX]."""
    context_parts: list[str] = []
    for i, chunk in enumerate(context_chunks, 1):
        authors = chunk.get("authors", "Unknown")
        year = chunk.get("year", "n.d.")
        page = chunk.get("page_number", "?")
        title = chunk.get("paper_title", "Untitled")
        text = chunk.get("text_content", "")
        context_parts.append(
            f"[Source {i}] {authors} ({year}), \"{title}\", p.{page}\n{text}"
        )

    context_block = "\n\n".join(context_parts)

    return (
        "You are an academic research assistant. Answer the following question "
        "based ONLY on the provided sources. Cite every claim using the format "
        "[Author, Year, p.XX]. If the sources do not contain enough information, "
        "state what is known and what remains unclear.\n\n"
        f"Question: {question}\n\n"
        f"Sources:\n{context_block}\n\n"
        "Answer:"
    )


def save_query(
    db_path: str,
    query_text: str,
    answer_text: str,
    cited_chunks: list[Any],
    confidence: float,
) -> int:
    """Persist a Q&A exchange to the queries table. Returns the new row id."""
    cited_refs = json.dumps([
        {"paper_id": c.get("paper_id"), "page_number": c.get("page_number")}
        for c in cited_chunks
    ])

    with get_db(db_path) as conn:
        cursor = conn.execute(
            "INSERT INTO queries (query_text, answer_text, cited_chunks, confidence) "
            "VALUES (?, ?, ?, ?)",
            (query_text, answer_text, cited_refs, confidence),
        )
        row_id: int = cursor.lastrowid  # type: ignore[assignment]

    logger.info("Saved query id=%d (confidence=%.3f)", row_id, confidence)
    return row_id
