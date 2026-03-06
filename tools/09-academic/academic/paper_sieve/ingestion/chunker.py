"""Section-aware text chunking for academic papers."""

from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger("openclaw.academic.paper_sieve.chunker")

_SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?])\s+(?=[A-Z\d])")


def _estimate_tokens(text: str) -> int:
    """Rough token count: split on whitespace, ~1.3 tokens per word for English."""
    words = text.split()
    return int(len(words) * 1.3)


def _split_sentences(text: str) -> list[str]:
    """Split text into sentences using a simple regex heuristic."""
    sentences = _SENTENCE_BOUNDARY.split(text)
    return [s.strip() for s in sentences if s.strip()]


def chunk_text(
    text: str,
    section_name: str,
    max_tokens: int = 500,
    overlap: int = 50,
) -> list[dict[str, Any]]:
    """Split a section's text into overlapping chunks respecting sentence boundaries.

    Returns a list of dicts:
        - text: chunk text content
        - section_name: originating section
        - token_count: estimated token count
        - chunk_index: sequential index within this section
    """
    if not text.strip():
        return []

    sentences = _split_sentences(text)
    if not sentences:
        return [{
            "text": text.strip(),
            "section_name": section_name,
            "token_count": _estimate_tokens(text),
            "chunk_index": 0,
        }]

    chunks: list[dict[str, Any]] = []
    current_sentences: list[str] = []
    current_tokens = 0

    for sentence in sentences:
        sent_tokens = _estimate_tokens(sentence)

        if current_tokens + sent_tokens > max_tokens and current_sentences:
            chunk_text_str = " ".join(current_sentences)
            chunks.append({
                "text": chunk_text_str,
                "section_name": section_name,
                "token_count": _estimate_tokens(chunk_text_str),
                "chunk_index": len(chunks),
            })

            overlap_sentences: list[str] = []
            overlap_tokens = 0
            for s in reversed(current_sentences):
                s_tokens = _estimate_tokens(s)
                if overlap_tokens + s_tokens > overlap:
                    break
                overlap_sentences.insert(0, s)
                overlap_tokens += s_tokens

            current_sentences = overlap_sentences
            current_tokens = overlap_tokens

        current_sentences.append(sentence)
        current_tokens += sent_tokens

    if current_sentences:
        chunk_text_str = " ".join(current_sentences)
        chunks.append({
            "text": chunk_text_str,
            "section_name": section_name,
            "token_count": _estimate_tokens(chunk_text_str),
            "chunk_index": len(chunks),
        })

    return chunks


def chunk_paper(sections: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Chunk all sections of a paper, returning a flat list with global indices.

    Each item in *sections* must have keys ``section_name`` and ``text``.
    Returns the combined chunk list with globally sequential ``chunk_index``.
    """
    all_chunks: list[dict[str, Any]] = []
    global_index = 0

    for section in sections:
        section_chunks = chunk_text(
            text=section["text"],
            section_name=section["section_name"],
        )
        for chunk in section_chunks:
            chunk["chunk_index"] = global_index
            all_chunks.append(chunk)
            global_index += 1

    logger.info(
        "Chunked %d sections into %d total chunks",
        len(sections),
        len(all_chunks),
    )
    return all_chunks
