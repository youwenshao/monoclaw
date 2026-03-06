"""Extract paper metadata from PDFs and DOI/CrossRef lookups."""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

import fitz  # PyMuPDF
import httpx

logger = logging.getLogger("openclaw.academic.paper_sieve.metadata_extractor")

_DOI_PATTERN = re.compile(r"(10\.\d{4,}/[^\s,;\"'}\]]+)")
_YEAR_PATTERN = re.compile(r"\b(19|20)\d{2}\b")
_AUTHOR_DELIMITERS = re.compile(r"\s*[,;&]\s*|\s+and\s+", re.IGNORECASE)

CROSSREF_API = "https://api.crossref.org/works"
CROSSREF_HEADERS = {"User-Agent": "OpenClaw-PaperSieve/1.0 (mailto:dev@openclaw.dev)"}


def _extract_title_from_blocks(blocks: list[dict[str, Any]]) -> str | None:
    """Pick the largest-font text block on the first page as the title."""
    if not blocks:
        return None
    candidates = [
        b for b in blocks
        if b.get("max_font_size", 0) > 0 and len(b.get("text", "")) > 5
    ]
    if not candidates:
        return None
    candidates.sort(key=lambda b: b["max_font_size"], reverse=True)
    title = candidates[0]["text"].replace("\n", " ").strip()
    if len(title) > 300:
        title = title[:300]
    return title


def _extract_abstract(full_text: str) -> str | None:
    """Try to extract the abstract from the first pages' text."""
    match = re.search(
        r"(?:^|\n)\s*Abstract[:\.\s]*\n?(.*?)(?:\n\s*(?:Keywords?|Introduction|1[\.\s])\b)",
        full_text,
        re.IGNORECASE | re.DOTALL,
    )
    if match:
        abstract = match.group(1).strip()
        abstract = re.sub(r"\s+", " ", abstract)
        return abstract if len(abstract) > 30 else None
    return None


def _extract_authors_heuristic(text: str) -> list[str]:
    """Attempt to extract author names from text between title and abstract."""
    match = re.search(
        r"(?:^|\n)((?:[A-Z][a-z]+(?:\s[A-Z]\.?\s?)?[A-Z][a-z]+)"
        r"(?:\s*[,;&]\s*(?:[A-Z][a-z]+(?:\s[A-Z]\.?\s?)?[A-Z][a-z]+))+)",
        text,
    )
    if match:
        raw = match.group(1)
        authors = [a.strip() for a in _AUTHOR_DELIMITERS.split(raw) if a.strip()]
        return authors[:30]
    return []


def extract_metadata_from_pdf(file_path: str | Path) -> dict[str, Any]:
    """Extract title, authors, abstract, DOI, and year from a PDF.

    Uses a combination of PDF document info, font-size heuristics, and
    regex patterns on the first few pages.
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"PDF not found: {path}")

    doc = fitz.open(str(path))
    metadata: dict[str, Any] = {
        "title": None,
        "authors": [],
        "abstract": None,
        "doi": None,
        "year": None,
        "total_pages": len(doc),
    }

    try:
        pdf_meta = doc.metadata or {}
        metadata["title"] = pdf_meta.get("title") or None
        if pdf_meta.get("author"):
            metadata["authors"] = [
                a.strip() for a in _AUTHOR_DELIMITERS.split(pdf_meta["author"]) if a.strip()
            ]

        pages_to_scan = min(3, len(doc))
        first_pages_text = ""
        first_page_blocks: list[dict[str, Any]] = []

        for i in range(pages_to_scan):
            page = doc[i]
            page_text = page.get_text()
            first_pages_text += page_text + "\n"

            if i == 0:
                from academic.paper_sieve.ingestion.pdf_parser import _extract_blocks

                first_page_blocks = _extract_blocks(page)

        if not metadata["title"] or len(metadata["title"]) < 5:
            metadata["title"] = _extract_title_from_blocks(first_page_blocks)

        if not metadata["authors"]:
            metadata["authors"] = _extract_authors_heuristic(first_pages_text[:2000])

        metadata["abstract"] = _extract_abstract(first_pages_text)

        doi_match = _DOI_PATTERN.search(first_pages_text[:5000])
        if doi_match:
            metadata["doi"] = doi_match.group(1).rstrip(".")

        if pdf_meta.get("creationDate"):
            year_match = _YEAR_PATTERN.search(pdf_meta["creationDate"])
            if year_match:
                metadata["year"] = int(year_match.group(0))

        if not metadata["year"]:
            year_match = _YEAR_PATTERN.search(first_pages_text[:3000])
            if year_match:
                metadata["year"] = int(year_match.group(0))
    finally:
        doc.close()

    return metadata


def extract_metadata_from_doi(doi: str) -> dict[str, Any]:
    """Fetch paper metadata from CrossRef using a DOI.

    Returns a dict with: title, authors, abstract, doi, year, journal, volume, pages.
    """
    metadata: dict[str, Any] = {
        "title": None,
        "authors": [],
        "abstract": None,
        "doi": doi,
        "year": None,
        "journal": None,
        "volume": None,
        "pages": None,
    }

    clean_doi = doi.strip().removeprefix("https://doi.org/").removeprefix("http://doi.org/")
    url = f"{CROSSREF_API}/{clean_doi}"

    try:
        resp = httpx.get(url, headers=CROSSREF_HEADERS, timeout=15.0, follow_redirects=True)
        resp.raise_for_status()
        data = resp.json().get("message", {})
    except (httpx.HTTPError, ValueError) as exc:
        logger.warning("CrossRef lookup failed for DOI %s: %s", doi, exc)
        return metadata

    titles = data.get("title", [])
    if titles:
        metadata["title"] = titles[0]

    for author in data.get("author", []):
        name_parts = []
        if author.get("given"):
            name_parts.append(author["given"])
        if author.get("family"):
            name_parts.append(author["family"])
        if name_parts:
            metadata["authors"].append(" ".join(name_parts))

    if data.get("abstract"):
        abstract = re.sub(r"<[^>]+>", "", data["abstract"]).strip()
        metadata["abstract"] = abstract

    date_parts = data.get("published-print", data.get("published-online", {})).get("date-parts")
    if date_parts and date_parts[0]:
        metadata["year"] = date_parts[0][0]

    container = data.get("container-title", [])
    if container:
        metadata["journal"] = container[0]

    metadata["volume"] = data.get("volume")
    metadata["pages"] = data.get("page")

    return metadata
