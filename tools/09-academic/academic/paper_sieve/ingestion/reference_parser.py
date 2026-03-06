"""Parse bibliography / reference sections from academic papers."""

from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger("openclaw.academic.paper_sieve.reference_parser")

_REF_NUM_PREFIX = re.compile(r"^\s*\[?\d{1,3}\]?[\.\)]\s*")
_DOI_PATTERN = re.compile(r"(10\.\d{4,}/[^\s,;\"'}\]]+)")
_YEAR_PATTERN = re.compile(r"\((\d{4})\)|,\s*(\d{4})[.,\s]")
_PAGES_PATTERN = re.compile(r"(?:pp?\.\s*)?(\d+)\s*[-–]\s*(\d+)")
_VOLUME_ISSUE = re.compile(r"(\d+)\s*\((\d+)\)")


def _split_references(text: str) -> list[str]:
    """Split a reference section into individual reference strings."""
    lines = text.strip().split("\n")
    refs: list[str] = []
    current: list[str] = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            if current:
                refs.append(" ".join(current))
                current = []
            continue

        if _REF_NUM_PREFIX.match(stripped):
            if current:
                refs.append(" ".join(current))
            current = [_REF_NUM_PREFIX.sub("", stripped)]
        elif re.match(r"^\s*\[", stripped) and current:
            refs.append(" ".join(current))
            current = [stripped]
        else:
            current.append(stripped)

    if current:
        refs.append(" ".join(current))

    if len(refs) <= 1 and text.strip():
        parts = re.split(r"\n\s*\n", text.strip())
        if len(parts) > 1:
            refs = [p.replace("\n", " ").strip() for p in parts if p.strip()]

    return refs


def _parse_authors(text: str) -> list[str]:
    """Extract author names from the beginning of a reference string."""
    year_match = re.search(r"\(\d{4}\)", text)
    if year_match:
        author_part = text[: year_match.start()].strip().rstrip(",").rstrip(".")
    else:
        parts = re.split(r"\.\s+(?=[A-Z])", text, maxsplit=1)
        author_part = parts[0] if parts else text[:100]

    author_part = author_part.strip().rstrip(".")
    authors = re.split(r"\s*[,;&]\s*|\s+and\s+", author_part, flags=re.IGNORECASE)
    cleaned: list[str] = []
    for a in authors:
        a = a.strip()
        if a and len(a) > 1 and not a.isdigit():
            cleaned.append(a)
    return cleaned[:30]


def _extract_title(text: str) -> str | None:
    """Try to extract the paper title from a reference string.

    Common patterns: after "(year). Title." or after authors. "Title."
    """
    match = re.search(r"\(\d{4}[a-z]?\)\.\s*(.+?)\.\s", text)
    if match:
        return match.group(1).strip()

    match = re.search(r""\s*(.+?)\s*"", text)
    if match:
        return match.group(1).strip()

    match = re.search(r'"(.+?)"', text)
    if match:
        return match.group(1).strip()

    return None


def _extract_journal(text: str) -> str | None:
    """Try to extract journal name (typically in italics context or after title)."""
    match = re.search(r"\.\s*([A-Z][^.]{5,80}?),?\s*\d+\s*[\(,]", text)
    if match:
        candidate = match.group(1).strip().rstrip(",")
        if not re.match(r"^\d", candidate):
            return candidate
    return None


def extract_references(text: str) -> list[dict[str, Any]]:
    """Parse a bibliography / references section into structured reference dicts.

    Returns a list of dicts with:
        - raw_text: the original reference string
        - authors: list of author name strings
        - title: extracted paper title (or None)
        - year: publication year (int or None)
        - journal: journal name (or None)
        - doi: DOI string (or None)
    """
    ref_strings = _split_references(text)
    parsed: list[dict[str, Any]] = []

    for raw in ref_strings:
        raw = raw.strip()
        if len(raw) < 10:
            continue

        entry: dict[str, Any] = {
            "raw_text": raw,
            "authors": _parse_authors(raw),
            "title": _extract_title(raw),
            "year": None,
            "journal": _extract_journal(raw),
            "doi": None,
        }

        year_match = _YEAR_PATTERN.search(raw)
        if year_match:
            year_str = year_match.group(1) or year_match.group(2)
            entry["year"] = int(year_str)

        doi_match = _DOI_PATTERN.search(raw)
        if doi_match:
            entry["doi"] = doi_match.group(1).rstrip(".")

        parsed.append(entry)

    logger.info("Parsed %d references from text", len(parsed))
    return parsed
