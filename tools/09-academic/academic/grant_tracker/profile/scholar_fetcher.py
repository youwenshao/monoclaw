"""Semantic Scholar integration – fetch publications and citation counts."""

from __future__ import annotations

import logging
from typing import Any

import httpx

logger = logging.getLogger("openclaw.academic.grant_tracker.profile.scholar")

SEMANTIC_SCHOLAR_API: str = "https://api.semanticscholar.org/graph/v1"
USER_AGENT = "MonoClaw GrantTracker/1.0"
_FIELDS = "title,authors,year,externalIds,citationCount,journal,publicationDate"


def fetch_publications(
    author_name: str = "",
    semantic_scholar_id: str = "",
) -> list[dict]:
    """Fetch publications from Semantic Scholar.

    Provide either *author_name* (free-text search) or
    *semantic_scholar_id* (direct author lookup).

    Returns a list of dicts with keys: title, authors, year, doi,
    citation_count, journal, semantic_scholar_id.
    """
    if semantic_scholar_id:
        return _fetch_by_author_id(semantic_scholar_id)
    if author_name:
        return _fetch_by_name(author_name)
    return []


def _fetch_by_author_id(author_id: str) -> list[dict]:
    url = f"{SEMANTIC_SCHOLAR_API}/author/{author_id}/papers"
    params = {"fields": _FIELDS, "limit": 500}

    try:
        with httpx.Client(
            headers={"User-Agent": USER_AGENT},
            timeout=30,
        ) as client:
            resp = client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPError as exc:
        logger.error("Semantic Scholar author papers fetch failed: %s", exc)
        return []

    return _normalize_papers(data.get("data", []))


def _fetch_by_name(name: str) -> list[dict]:
    search_url = f"{SEMANTIC_SCHOLAR_API}/author/search"
    try:
        with httpx.Client(
            headers={"User-Agent": USER_AGENT},
            timeout=30,
        ) as client:
            resp = client.get(search_url, params={"query": name, "limit": 5})
            resp.raise_for_status()
            authors = resp.json().get("data", [])

            if not authors:
                logger.info("No Semantic Scholar authors found for '%s'", name)
                return []

            author_id = authors[0]["authorId"]
            logger.info(
                "Matched '%s' to Semantic Scholar author %s (%s)",
                name, author_id, authors[0].get("name"),
            )
            return _fetch_by_author_id(author_id)

    except httpx.HTTPError as exc:
        logger.error("Semantic Scholar author search failed: %s", exc)
        return []


def _normalize_papers(papers: list[dict[str, Any]]) -> list[dict]:
    results: list[dict] = []
    for p in papers:
        ext_ids = p.get("externalIds") or {}
        authors_list = p.get("authors") or []
        author_names = ", ".join(a.get("name", "") for a in authors_list)
        journal_info = p.get("journal") or {}

        results.append({
            "title": p.get("title", ""),
            "authors": author_names,
            "year": p.get("year"),
            "doi": ext_ids.get("DOI"),
            "citation_count": p.get("citationCount", 0),
            "journal": journal_info.get("name", ""),
            "semantic_scholar_id": p.get("paperId", ""),
        })
    return results


def fetch_citation_count(doi: str) -> int | None:
    """Get the citation count for a single paper by DOI.

    Returns the count or None if the paper is not found.
    """
    url = f"{SEMANTIC_SCHOLAR_API}/paper/DOI:{doi}"
    params = {"fields": "citationCount"}

    try:
        with httpx.Client(
            headers={"User-Agent": USER_AGENT},
            timeout=15,
        ) as client:
            resp = client.get(url, params=params)
            if resp.status_code == 404:
                logger.info("Paper DOI:%s not found on Semantic Scholar", doi)
                return None
            resp.raise_for_status()
            data = resp.json()
            return data.get("citationCount")
    except httpx.HTTPError as exc:
        logger.error("Semantic Scholar citation fetch failed for DOI:%s – %s", doi, exc)
        return None
