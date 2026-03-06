"""Harvard citation style formatter."""

from __future__ import annotations

from typing import Any


def format_harvard(citation: dict[str, Any]) -> str:
    """Format a citation in Harvard style.

    Pattern: Author, I. (Year) Title. *Journal*, Volume(Issue), pp. Pages.
             Available at: https://doi.org/xxx.
    """
    parts: list[str] = []

    authors = citation.get("authors", [])
    author_str = _format_harvard_authors(authors)
    if author_str:
        parts.append(author_str)

    year = citation.get("year")
    parts.append(f"({year})" if year else "(no date)")

    title = citation.get("title", "")
    entry_type = citation.get("entry_type", "article")

    if entry_type in ("book", "chapter", "report", "thesis"):
        parts.append(f"*{title}*.")
    else:
        parts.append(f"'{title}',")

    journal = citation.get("journal")
    if journal:
        journal_part = f"*{journal}*"
        volume = citation.get("volume")
        issue = citation.get("issue")
        pages = citation.get("pages")

        if volume:
            journal_part += f", {volume}"
            if issue:
                journal_part += f"({issue})"
        if pages:
            journal_part += f", pp. {pages}"
        journal_part += "."
        parts.append(journal_part)

    publisher = citation.get("publisher")
    if publisher and entry_type in ("book", "chapter", "report"):
        parts.append(f"{publisher}.")

    doi = citation.get("doi")
    if doi:
        parts.append(f"Available at: https://doi.org/{doi}.")

    return " ".join(parts)


def format_harvard_in_text(citation: dict[str, Any]) -> str:
    """Return a Harvard in-text citation: (Author, Year) or (Author et al., Year)."""
    authors = citation.get("authors", [])
    year = citation.get("year", "no date")

    if not authors:
        name = citation.get("title", "Unknown")[:30]
    elif len(authors) == 1:
        name = _surname(authors[0])
    elif len(authors) == 2:
        name = f"{_surname(authors[0])} and {_surname(authors[1])}"
    elif len(authors) == 3:
        name = f"{_surname(authors[0])}, {_surname(authors[1])} and {_surname(authors[2])}"
    else:
        name = f"{_surname(authors[0])} et al."

    return f"({name}, {year})"


def _format_harvard_authors(authors: list[dict[str, str | None]]) -> str:
    """Format author list for Harvard reference list."""
    if not authors:
        return ""

    formatted = [_harvard_author_name(a) for a in authors]

    if len(formatted) == 1:
        return formatted[0]

    if len(formatted) <= 3:
        return ", ".join(formatted[:-1]) + f" and {formatted[-1]}"

    return f"{formatted[0]} et al."


def _harvard_author_name(author: dict[str, str | None]) -> str:
    """Format a single author: Family, I."""
    family = author.get("family", "")
    given = author.get("given")
    if not given:
        return family
    initials = _initials(given)
    return f"{family}, {initials}"


def _surname(author: dict[str, str | None]) -> str:
    return author.get("family", author.get("name_tc", "Unknown"))


def _initials(given: str) -> str:
    """Convert given names to initials: 'Tai Man' -> 'T.M.'"""
    parts = given.replace("-", " ").split()
    return "".join(f"{p[0].upper()}." for p in parts if p)
