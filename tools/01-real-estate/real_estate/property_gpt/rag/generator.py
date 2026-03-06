"""RAG answer generation with citations for PropertyGPT."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import AsyncIterator

from openclaw_shared.llm.base import LLMProvider

from real_estate.property_gpt.rag.retriever import search_buildings

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
You are PropertyGPT, an expert Hong Kong real estate assistant.
Answer the user's question using ONLY the provided building data as context.
Always cite sources using [Building Name] notation.
If you lack information, say so honestly. Respond in the same language as the query.
Prices should be in HKD. Use saleable area (not gross) as the primary area metric.\
"""


def _build_context(results: list[dict]) -> str:
    """Format retrieved building results as numbered context blocks."""
    if not results:
        return "No matching buildings found in the database."
    lines: list[str] = []
    for i, r in enumerate(results, 1):
        name = r.get("name_en") or r.get("name_zh") or f"Building {r.get('id', '?')}"
        lines.append(f"[{i}] {name}")
        lines.append(r.get("text", ""))
        lines.append("")
    return "\n".join(lines)


def _make_prompt(query: str, context: str) -> str:
    return (
        f"Context (retrieved buildings):\n{context}\n\n"
        f"User question: {query}\n\n"
        "Provide a helpful, detailed answer with citations."
    )


async def generate_answer(
    llm: LLMProvider,
    db_path: str | Path,
    query: str,
    *,
    limit: int = 5,
) -> str:
    """Retrieve context and generate a complete answer."""
    results = await search_buildings(llm, db_path, query, limit=limit)
    context = _build_context(results)
    prompt = _make_prompt(query, context)
    return await llm.generate(prompt, system=SYSTEM_PROMPT, max_tokens=1024, temperature=0.4)


async def stream_answer(
    llm: LLMProvider,
    db_path: str | Path,
    query: str,
    *,
    limit: int = 5,
) -> AsyncIterator[str]:
    """Retrieve context and stream the answer token-by-token."""
    results = await search_buildings(llm, db_path, query, limit=limit)
    context = _build_context(results)
    prompt = _make_prompt(query, context)
    async for token in llm.generate_stream(prompt, system=SYSTEM_PROMPT, max_tokens=1024, temperature=0.4):
        yield token
