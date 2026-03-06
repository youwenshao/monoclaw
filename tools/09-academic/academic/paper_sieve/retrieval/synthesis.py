"""Multi-paper synthesis: aggregate findings across papers on a topic."""

from __future__ import annotations

import json
import logging
from collections import defaultdict
from typing import Any

from academic.paper_sieve.retrieval.search_engine import semantic_search

logger = logging.getLogger("openclaw.academic.paper_sieve.synthesis")


def synthesize_across_papers(
    db_path: str,
    chroma_path: str,
    topic: str,
    llm: Any,
    n_papers: int = 5,
    model_name: str = "paraphrase-multilingual-MiniLM-L12-v2",
) -> dict[str, Any]:
    """Search for *topic*, group results by paper, and synthesize findings.

    Returns a dict with keys: synthesis, papers_used, key_findings.
    """
    chunks = semantic_search(
        db_path, chroma_path, topic,
        n_results=n_papers * 3,
        model_name=model_name,
    )

    if not chunks:
        return {"synthesis": "No relevant papers found.", "papers_used": [], "key_findings": []}

    paper_chunks: dict[str, list[dict[str, Any]]] = defaultdict(list)
    seen_papers: dict[str, dict[str, Any]] = {}
    for c in chunks:
        key = str(c.get("paper_id", "unknown"))
        paper_chunks[key].append(c)
        if key not in seen_papers:
            seen_papers[key] = {
                "paper_id": c.get("paper_id"),
                "paper_title": c.get("paper_title", ""),
                "authors": c.get("authors", ""),
                "year": c.get("year"),
            }

    top_paper_keys = list(seen_papers.keys())[:n_papers]
    filtered_chunks = {k: paper_chunks[k] for k in top_paper_keys}

    prompt = _build_synthesis_prompt(topic, filtered_chunks)
    raw_synthesis = llm.generate(prompt)

    lines = [ln.strip() for ln in raw_synthesis.split("\n") if ln.strip()]
    key_findings = [ln for ln in lines if ln.startswith("-") or ln.startswith("•")]
    if not key_findings:
        key_findings = lines[:5]

    return {
        "synthesis": raw_synthesis,
        "papers_used": [seen_papers[k] for k in top_paper_keys],
        "key_findings": key_findings,
    }


def _build_synthesis_prompt(
    topic: str,
    paper_chunks: dict[str, list[dict[str, Any]]],
) -> str:
    """Build a prompt asking the LLM to synthesize findings across papers."""
    sections: list[str] = []
    for paper_key, chunks in paper_chunks.items():
        if not chunks:
            continue
        first = chunks[0]
        header = (
            f"Paper: {first.get('paper_title', 'Untitled')} "
            f"({first.get('authors', 'Unknown')}, {first.get('year', 'n.d.')})"
        )
        excerpts = "\n".join(c.get("text_content", "")[:500] for c in chunks)
        sections.append(f"{header}\nExcerpts:\n{excerpts}")

    papers_block = "\n\n---\n\n".join(sections)

    return (
        "You are an academic research assistant performing a literature synthesis. "
        "Given the following excerpts from multiple papers on the topic below, "
        "write a coherent synthesis that:\n"
        "1. Identifies common themes and agreements across papers\n"
        "2. Notes contradictions or debates\n"
        "3. Highlights gaps in the literature\n"
        "Cite sources as [Author, Year]. Use bullet points for key findings.\n\n"
        f"Topic: {topic}\n\n"
        f"Papers:\n{papers_block}\n\n"
        "Synthesis:"
    )
