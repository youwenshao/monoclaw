"""DOI validation and metadata retrieval via CrossRef and Semantic Scholar."""

from __future__ import annotations

import re
from typing import Any

import httpx

_DOI_REGEX = re.compile(r"^10\.\d{4,}/\S+$")
_CROSSREF_API = "https://api.crossref.org/works/"
_SEMANTIC_SCHOLAR_API = "https://api.semanticscholar.org/graph/v1/paper/DOI:"

_TIMEOUT = httpx.Timeout(15.0, connect=10.0)


async def validate_doi(doi: str) -> bool:
    """Check whether a DOI resolves via doi.org (HTTP HEAD)."""
    doi = doi.strip()
    if not _DOI_REGEX.match(doi):
        return False
    url = f"https://doi.org/{doi}"
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT, follow_redirects=True) as client:
            resp = await client.head(url)
            return resp.status_code < 400
    except httpx.HTTPError:
        return False


async def fetch_crossref_metadata(doi: str, email: str = "") -> dict[str, Any]:
    """Fetch full metadata from the CrossRef API for a given DOI.

    Passing an email enables the CrossRef polite pool for better rate limits.
    """
    doi = doi.strip()
    headers: dict[str, str] = {"Accept": "application/json"}
    if email:
        headers["User-Agent"] = f"CiteBot/1.0 (mailto:{email})"

    async with httpx.AsyncClient(timeout=_TIMEOUT, headers=headers) as client:
        resp = await client.get(f"{_CROSSREF_API}{doi}")
        resp.raise_for_status()
        data = resp.json()

    message = data.get("message", {})
    return _crossref_to_citation(message)


async def fetch_semantic_scholar(doi: str) -> dict[str, Any]:
    """Fetch metadata from Semantic Scholar as a fallback source."""
    doi = doi.strip()
    fields = "title,authors,year,venue,externalIds,publicationTypes,journal"
    url = f"{_SEMANTIC_SCHOLAR_API}{doi}?fields={fields}"

    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        data = resp.json()

    return _s2_to_citation(data)


async def resolve_doi(doi: str, email: str = "") -> dict[str, Any]:
    """Resolve a DOI by trying CrossRef first, then Semantic Scholar."""
    doi = doi.strip()
    try:
        return await fetch_crossref_metadata(doi, email=email)
    except (httpx.HTTPError, KeyError, ValueError):
        pass

    try:
        return await fetch_semantic_scholar(doi)
    except (httpx.HTTPError, KeyError, ValueError):
        pass

    return {
        "title": None,
        "authors": [],
        "year": None,
        "journal": None,
        "volume": None,
        "issue": None,
        "pages": None,
        "doi": doi,
        "entry_type": "article",
        "metadata_source": "unresolved",
    }


def _crossref_to_citation(msg: dict[str, Any]) -> dict[str, Any]:
    """Map CrossRef API message to a normalised citation dict."""
    authors: list[dict[str, str | None]] = []
    for a in msg.get("author", []):
        authors.append({
            "family": a.get("family", ""),
            "given": a.get("given"),
            "name_tc": None,
        })

    title_list = msg.get("title", [])
    title = title_list[0] if title_list else None

    date_parts = msg.get("issued", {}).get("date-parts", [[None]])
    year = date_parts[0][0] if date_parts and date_parts[0] else None

    journal_list = msg.get("container-title", [])
    journal = journal_list[0] if journal_list else None

    page = msg.get("page", "")
    if page:
        page = page.replace("–", "-")

    cr_type = msg.get("type", "")
    entry_type = _map_crossref_type(cr_type)

    return {
        "title": title,
        "authors": authors,
        "year": int(year) if year else None,
        "journal": journal,
        "volume": msg.get("volume"),
        "issue": msg.get("issue"),
        "pages": page or None,
        "doi": msg.get("DOI", ""),
        "entry_type": entry_type,
        "publisher": msg.get("publisher"),
        "url": msg.get("URL"),
        "metadata_source": "crossref",
    }


def _s2_to_citation(data: dict[str, Any]) -> dict[str, Any]:
    """Map Semantic Scholar API response to a normalised citation dict."""
    authors: list[dict[str, str | None]] = []
    for a in data.get("authors", []):
        name = a.get("name", "")
        tokens = name.split()
        if len(tokens) >= 2:
            family = tokens[-1]
            given = " ".join(tokens[:-1])
        else:
            family = name
            given = None
        authors.append({"family": family, "given": given, "name_tc": None})

    journal_info = data.get("journal") or {}

    return {
        "title": data.get("title"),
        "authors": authors,
        "year": data.get("year"),
        "journal": journal_info.get("name") or data.get("venue"),
        "volume": journal_info.get("volume"),
        "issue": None,
        "pages": journal_info.get("pages"),
        "doi": (data.get("externalIds") or {}).get("DOI", ""),
        "entry_type": "article",
        "publisher": None,
        "url": None,
        "metadata_source": "semantic_scholar",
    }


_CROSSREF_TYPE_MAP: dict[str, str] = {
    "journal-article": "article",
    "book": "book",
    "book-chapter": "chapter",
    "proceedings-article": "conference",
    "dissertation": "thesis",
    "report": "report",
    "posted-content": "other",
    "monograph": "book",
}


def _map_crossref_type(cr_type: str) -> str:
    return _CROSSREF_TYPE_MAP.get(cr_type, "other")
