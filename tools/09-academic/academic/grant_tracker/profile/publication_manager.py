"""Publication list management – add, query, update, and format publications."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from openclaw_shared.database import get_db

logger = logging.getLogger("openclaw.academic.grant_tracker.profile.publications")


def add_publication(
    db_path: str | Path,
    researcher_id: int,
    title: str,
    authors: str,
    journal: str,
    year: int,
    **kwargs: Any,
) -> int:
    """Insert a publication and return its ID.

    Keyword args can include: doi, citation_count, is_corresponding_author.
    """
    with get_db(db_path) as conn:
        cur = conn.execute(
            """INSERT INTO publications
               (researcher_id, title, authors, journal, year, doi,
                citation_count, is_corresponding_author)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                researcher_id,
                title,
                authors,
                journal,
                year,
                kwargs.get("doi"),
                kwargs.get("citation_count", 0),
                kwargs.get("is_corresponding_author", False),
            ),
        )
        pub_id: int = cur.lastrowid  # type: ignore[assignment]
    return pub_id


def get_publications(
    db_path: str | Path,
    researcher_id: int,
    year_from: int | None = None,
) -> list[dict]:
    """Return publications for a researcher, optionally filtered by year.

    Results are ordered by year descending, then title.
    """
    query = "SELECT * FROM publications WHERE researcher_id = ?"
    params: list[Any] = [researcher_id]

    if year_from is not None:
        query += " AND year >= ?"
        params.append(year_from)

    query += " ORDER BY year DESC, title ASC"

    with get_db(db_path) as conn:
        rows = conn.execute(query, params).fetchall()

    return [dict(r) for r in rows]


def update_citation_counts(
    db_path: str | Path,
    researcher_id: int,
    publications: list[dict],
) -> int:
    """Bulk-update citation counts for a researcher's publications.

    Each dict in *publications* should have at least ``doi`` or ``title``
    (for matching) and ``citation_count``.

    Returns the number of rows updated.
    """
    updated = 0
    with get_db(db_path) as conn:
        for pub in publications:
            count = pub.get("citation_count")
            if count is None:
                continue

            doi = pub.get("doi")
            title = pub.get("title")

            if doi:
                cur = conn.execute(
                    """UPDATE publications
                       SET citation_count = ?, last_updated = CURRENT_TIMESTAMP
                       WHERE researcher_id = ? AND doi = ?""",
                    (count, researcher_id, doi),
                )
            elif title:
                cur = conn.execute(
                    """UPDATE publications
                       SET citation_count = ?, last_updated = CURRENT_TIMESTAMP
                       WHERE researcher_id = ? AND title = ?""",
                    (count, researcher_id, title),
                )
            else:
                continue

            updated += cur.rowcount

    logger.info("Updated citation counts for %d publications (researcher %d)", updated, researcher_id)
    return updated


def format_publications_for_rgc(publications: list[dict]) -> str:
    """Format a list of publication dicts in RGC-standard style.

    Output format per entry::

        1. Authors* (Year). Title. Journal. DOI: xxx. [Citations: N]

    The asterisk marks the corresponding author entry.
    """
    if not publications:
        return ""

    lines: list[str] = []
    for i, p in enumerate(publications, 1):
        authors = p.get("authors", "")
        corr = " *" if p.get("is_corresponding_author") else ""
        year = p.get("year", "")
        title = p.get("title", "")
        journal = p.get("journal", "")
        doi = p.get("doi", "")
        citations = p.get("citation_count")

        entry = f"{i}. {authors}{corr} ({year}). {title}. {journal}."
        if doi:
            entry += f" DOI: {doi}."
        if citations is not None:
            entry += f" [Citations: {citations}]"
        lines.append(entry)

    return "\n".join(lines)
