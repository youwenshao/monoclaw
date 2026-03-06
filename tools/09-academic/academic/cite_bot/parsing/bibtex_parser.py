"""BibTeX file import — parse .bib content into structured citation dicts."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any


def parse_bibtex(content: str) -> list[dict[str, Any]]:
    """Parse a BibTeX string into a list of citation dicts.

    Each dict contains: title, authors, year, journal, volume, issue, pages,
    doi, entry_type, publisher, url, and the raw bibtex_key.
    """
    entries: list[dict[str, Any]] = []
    for match in re.finditer(
        r"@(\w+)\s*\{\s*([^,\s]*)\s*,(.*?)\n\s*\}",
        content,
        re.DOTALL,
    ):
        entry_type_raw = match.group(1).lower()
        bibtex_key = match.group(2).strip()
        body = match.group(3)

        fields = _parse_fields(body)
        entry_type = _map_entry_type(entry_type_raw)
        authors = _parse_bibtex_authors(fields.get("author", ""))

        entry: dict[str, Any] = {
            "title": _clean_braces(fields.get("title", "")),
            "authors": authors,
            "year": _safe_int(fields.get("year")),
            "journal": _clean_braces(fields.get("journal", "")) or _clean_braces(fields.get("booktitle", "")),
            "volume": fields.get("volume"),
            "issue": fields.get("number"),
            "pages": _normalise_pages(fields.get("pages", "")),
            "doi": fields.get("doi", "").strip(),
            "entry_type": entry_type,
            "publisher": _clean_braces(fields.get("publisher", "")),
            "url": fields.get("url", "").strip(),
            "bibtex_key": bibtex_key,
        }
        entries.append(entry)

    return entries


def parse_bibtex_file(file_path: str | Path) -> list[dict[str, Any]]:
    """Read a .bib file from disk and parse its content."""
    path = Path(file_path)
    content = path.read_text(encoding="utf-8")
    return parse_bibtex(content)


def _parse_fields(body: str) -> dict[str, str]:
    """Extract key-value pairs from the BibTeX entry body."""
    fields: dict[str, str] = {}
    for m in re.finditer(
        r"(\w+)\s*=\s*(?:\{((?:[^{}]|\{[^{}]*\})*)\}|\"((?:[^\"]|\\\")*)\"|(\d+))",
        body,
    ):
        key = m.group(1).lower()
        value = m.group(2) if m.group(2) is not None else (m.group(3) if m.group(3) is not None else m.group(4))
        fields[key] = value.strip() if value else ""
    return fields


def _parse_bibtex_authors(author_str: str) -> list[dict[str, str | None]]:
    """Parse a BibTeX author field ('Last, First and Last, First') into structured dicts."""
    if not author_str.strip():
        return []

    author_str = _clean_braces(author_str)
    parts = re.split(r"\s+and\s+", author_str, flags=re.IGNORECASE)
    authors: list[dict[str, str | None]] = []

    for part in parts:
        part = part.strip()
        if not part:
            continue

        name_tc: str | None = None
        chinese_match = re.search(r"[\u4e00-\u9fff]+", part)
        if chinese_match:
            name_tc = chinese_match.group()

        if "," in part:
            segments = part.split(",", 1)
            family = segments[0].strip()
            given = segments[1].strip() or None
        else:
            tokens = part.split()
            if len(tokens) == 1:
                family = tokens[0]
                given = None
            else:
                family = tokens[-1]
                given = " ".join(tokens[:-1])

        authors.append({"family": family, "given": given, "name_tc": name_tc})

    return authors


def _clean_braces(text: str) -> str:
    """Remove surrounding and nested LaTeX braces."""
    text = text.strip()
    text = re.sub(r"[{}]", "", text)
    return text.strip()


def _normalise_pages(pages: str) -> str:
    """Normalise page ranges to use hyphens."""
    if not pages:
        return ""
    return re.sub(r"\s*[-–—]+\s*", "-", pages.strip())


def _safe_int(value: str | None) -> int | None:
    if value and value.strip().isdigit():
        return int(value.strip())
    return None


_ENTRY_TYPE_MAP: dict[str, str] = {
    "article": "article",
    "inproceedings": "conference",
    "conference": "conference",
    "book": "book",
    "inbook": "chapter",
    "incollection": "chapter",
    "phdthesis": "thesis",
    "mastersthesis": "thesis",
    "techreport": "report",
    "misc": "other",
    "online": "website",
    "unpublished": "other",
}


def _map_entry_type(bibtex_type: str) -> str:
    return _ENTRY_TYPE_MAP.get(bibtex_type, "other")
