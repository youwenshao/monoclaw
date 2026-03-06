"""Find duplicate references in a citation list using title and DOI matching."""

from __future__ import annotations

import re
import unicodedata
from typing import Any


def find_duplicates(citations: list[dict[str, Any]]) -> list[tuple[int, int, str]]:
    """Return a list of (index_a, index_b, match_reason) for probable duplicate pairs.

    Detection passes:
    1. Exact DOI match (most reliable).
    2. High title similarity (threshold >= 0.85).
    3. Same authors + year with moderate title similarity (>= 0.70).
    """
    n = len(citations)
    seen: set[tuple[int, int]] = set()
    duplicates: list[tuple[int, int, str]] = []

    doi_index: dict[str, list[int]] = {}
    for i, c in enumerate(citations):
        doi = (c.get("doi") or "").strip().lower()
        if doi:
            doi_index.setdefault(doi, []).append(i)

    for doi, indices in doi_index.items():
        if len(indices) > 1:
            for a_idx in range(len(indices)):
                for b_idx in range(a_idx + 1, len(indices)):
                    pair = (indices[a_idx], indices[b_idx])
                    if pair not in seen:
                        seen.add(pair)
                        duplicates.append((*pair, f"exact DOI match: {doi}"))

    for i in range(n):
        title_i = citations[i].get("title", "")
        year_i = citations[i].get("year")
        authors_i = _author_key(citations[i].get("authors", []))

        for j in range(i + 1, n):
            if (i, j) in seen:
                continue

            title_j = citations[j].get("title", "")
            sim = title_similarity(title_i, title_j)

            if sim >= 0.85:
                seen.add((i, j))
                duplicates.append((i, j, f"high title similarity ({sim:.2f})"))
                continue

            if sim >= 0.70 and year_i and year_i == citations[j].get("year"):
                authors_j = _author_key(citations[j].get("authors", []))
                if authors_i and authors_i == authors_j:
                    seen.add((i, j))
                    duplicates.append((i, j, f"same authors+year, similar title ({sim:.2f})"))

    return duplicates


def title_similarity(a: str, b: str) -> float:
    """Normalised string similarity score between two titles.

    Uses bigram (character 2-gram) Dice coefficient on normalised strings.
    Returns a float in [0.0, 1.0].
    """
    a_norm = _normalise_text(a)
    b_norm = _normalise_text(b)

    if a_norm == b_norm:
        return 1.0
    if not a_norm or not b_norm:
        return 0.0

    bigrams_a = _bigrams(a_norm)
    bigrams_b = _bigrams(b_norm)

    if not bigrams_a or not bigrams_b:
        return 0.0

    intersection = bigrams_a & bigrams_b
    return 2.0 * sum(intersection.values()) / (sum(bigrams_a.values()) + sum(bigrams_b.values()))


def _normalise_text(text: str) -> str:
    """Lowercase, strip accents, remove punctuation, collapse whitespace."""
    text = text.lower().strip()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = re.sub(r"[^\w\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _bigrams(text: str) -> dict[str, int]:
    """Return a multiset (Counter-like dict) of character bigrams."""
    counts: dict[str, int] = {}
    for i in range(len(text) - 1):
        bg = text[i : i + 2]
        counts[bg] = counts.get(bg, 0) + 1
    return counts


def _author_key(authors: list[dict[str, str | None]]) -> str:
    """Create a normalised key from author family names for quick comparison."""
    families = sorted(
        _normalise_text(a.get("family", "")) for a in authors if a.get("family")
    )
    return "|".join(families)
