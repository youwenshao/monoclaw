"""APA 7th edition citation formatter."""

from __future__ import annotations

from typing import Any


def format_apa7(citation: dict[str, Any]) -> str:
    """Format a citation in APA 7th edition style.

    Pattern: Author, A. A., & Author, B. B. (Year). Title. *Journal*, *Volume*(Issue), Pages.
             https://doi.org/xxx
    """
    parts: list[str] = []

    authors = citation.get("authors", [])
    author_str = _format_apa_authors(authors)
    if author_str:
        parts.append(author_str)

    year = citation.get("year")
    if year:
        parts.append(f"({year}).")
    else:
        parts.append("(n.d.).")

    title = citation.get("title", "")
    entry_type = citation.get("entry_type", "article")

    if entry_type == "article":
        parts.append(f"{title}.")
    else:
        parts.append(f"*{title}*.")

    journal = citation.get("journal")
    if journal:
        volume = citation.get("volume")
        issue = citation.get("issue")
        pages = citation.get("pages")

        journal_part = f"*{journal}*"
        if volume:
            journal_part += f", *{volume}*"
            if issue:
                journal_part += f"({issue})"
        if pages:
            journal_part += f", {pages}"
        journal_part += "."
        parts.append(journal_part)

    publisher = citation.get("publisher")
    if publisher and entry_type in ("book", "chapter", "report"):
        parts.append(f"{publisher}.")

    doi = citation.get("doi")
    if doi:
        parts.append(f"https://doi.org/{doi}")

    return " ".join(parts)


def format_apa7_in_text(citation: dict[str, Any], narrative: bool = False) -> str:
    """Return an in-text citation: '(Author, Year)' or 'Author (Year)' for narrative."""
    authors = citation.get("authors", [])
    year = citation.get("year", "n.d.")

    if not authors:
        name = citation.get("title", "Unknown")[:30]
    elif len(authors) == 1:
        name = _apa_surname(authors[0])
    elif len(authors) == 2:
        name = f"{_apa_surname(authors[0])} & {_apa_surname(authors[1])}"
    else:
        name = f"{_apa_surname(authors[0])} et al."

    if narrative:
        return f"{name} ({year})"
    return f"({name}, {year})"


def _format_apa_authors(authors: list[dict[str, str | None]]) -> str:
    """Format author list for APA 7th reference list.

    1 author: Wong, T. M.
    2 authors: Wong, T. M., & Chan, S. Y.
    3-20 authors: all listed, with & before last
    21+ authors: first 19 ... last
    """
    if not authors:
        return ""

    formatted = [_apa_author_name(a) for a in authors]

    if len(formatted) == 1:
        return f"{formatted[0]}."

    if len(formatted) == 2:
        return f"{formatted[0]}, & {formatted[1]}."

    if len(formatted) <= 20:
        return ", ".join(formatted[:-1]) + f", & {formatted[-1]}."

    return ", ".join(formatted[:19]) + f", ... {formatted[-1]}."


def _apa_author_name(author: dict[str, str | None]) -> str:
    """Format a single author: Family, G. I. (initials)."""
    family = author.get("family", "")
    given = author.get("given")
    if not given:
        return family
    initials = _initials(given)
    return f"{family}, {initials}"


def _apa_surname(author: dict[str, str | None]) -> str:
    """Return just the family name for in-text use."""
    return author.get("family", author.get("name_tc", "Unknown"))


def _initials(given: str) -> str:
    """Convert given names to APA-style initials: 'Tai Man' -> 'T. M.'"""
    parts = given.replace("-", " ").split()
    return " ".join(f"{p[0].upper()}." for p in parts if p)
