"""RIS file import — parse .ris content into structured citation dicts."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any


_RIS_TYPE_MAP: dict[str, str] = {
    "JOUR": "article",
    "BOOK": "book",
    "CHAP": "chapter",
    "CONF": "conference",
    "CPAPER": "conference",
    "THES": "thesis",
    "RPRT": "report",
    "ELEC": "website",
    "GEN": "other",
    "MGZN": "article",
    "NEWS": "article",
}


def parse_ris(content: str) -> list[dict[str, Any]]:
    """Parse an RIS string into a list of citation dicts.

    Each dict contains: title, authors, year, journal, volume, issue, pages,
    doi, entry_type, publisher, url, abstract, and keywords.
    """
    entries: list[dict[str, Any]] = []
    current: dict[str, list[str]] = {}

    for line in content.splitlines():
        line = line.rstrip()

        if re.match(r"^ER\s+-", line):
            if current:
                entries.append(_build_entry(current))
                current = {}
            continue

        match = re.match(r"^([A-Z][A-Z0-9])\s+-\s+(.*)", line)
        if match:
            tag = match.group(1)
            value = match.group(2).strip()
            current.setdefault(tag, []).append(value)

    if current:
        entries.append(_build_entry(current))

    return entries


def parse_ris_file(file_path: str | Path) -> list[dict[str, Any]]:
    """Read a .ris file from disk and parse its content."""
    path = Path(file_path)
    content = path.read_text(encoding="utf-8")
    return parse_ris(content)


def _build_entry(fields: dict[str, list[str]]) -> dict[str, Any]:
    """Convert collected RIS tag-value pairs into a citation dict."""
    ris_type = _first(fields, "TY")
    entry_type = _RIS_TYPE_MAP.get(ris_type, "other") if ris_type else "other"

    authors = _parse_ris_authors(fields.get("AU", []) + fields.get("A1", []))

    year: int | None = None
    py = _first(fields, "PY") or _first(fields, "Y1") or _first(fields, "DA")
    if py:
        year_match = re.search(r"\d{4}", py)
        if year_match:
            year = int(year_match.group())

    sp = _first(fields, "SP")
    ep = _first(fields, "EP")
    pages = ""
    if sp and ep:
        pages = f"{sp}-{ep}"
    elif sp:
        pages = sp

    return {
        "title": _first(fields, "TI") or _first(fields, "T1") or "",
        "authors": authors,
        "year": year,
        "journal": _first(fields, "JO") or _first(fields, "JF") or _first(fields, "T2") or "",
        "volume": _first(fields, "VL") or "",
        "issue": _first(fields, "IS") or "",
        "pages": pages,
        "doi": _first(fields, "DO") or _extract_doi_from_urls(fields.get("UR", [])),
        "entry_type": entry_type,
        "publisher": _first(fields, "PB") or "",
        "url": _first(fields, "UR") or "",
        "abstract": _first(fields, "AB") or _first(fields, "N2") or "",
        "keywords": fields.get("KW", []),
    }


def _parse_ris_authors(author_values: list[str]) -> list[dict[str, str | None]]:
    """Parse RIS author lines ('Last, First' or 'First Last') into structured dicts."""
    authors: list[dict[str, str | None]] = []
    for raw in author_values:
        raw = raw.strip()
        if not raw:
            continue

        name_tc: str | None = None
        chinese_match = re.search(r"[\u4e00-\u9fff]+", raw)
        if chinese_match:
            name_tc = chinese_match.group()

        if "," in raw:
            parts = raw.split(",", 1)
            family = parts[0].strip()
            given = parts[1].strip() or None
        else:
            tokens = raw.split()
            if len(tokens) == 1:
                family = tokens[0]
                given = None
            else:
                family = tokens[-1]
                given = " ".join(tokens[:-1])

        authors.append({"family": family, "given": given, "name_tc": name_tc})

    return authors


def _first(fields: dict[str, list[str]], tag: str) -> str:
    """Return the first value for a tag or empty string."""
    vals = fields.get(tag, [])
    return vals[0].strip() if vals else ""


def _extract_doi_from_urls(urls: list[str]) -> str:
    """Try to extract a DOI from URL fields."""
    for url in urls:
        match = re.search(r"10\.\d{4,}/\S+", url)
        if match:
            return match.group().rstrip(".")
    return ""
