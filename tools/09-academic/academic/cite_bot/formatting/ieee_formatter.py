"""IEEE numbered citation style formatter."""

from __future__ import annotations

from typing import Any


def format_ieee(citation: dict[str, Any], number: int = 1) -> str:
    """Format a citation in IEEE style.

    Pattern: [N] A. B. Author and C. D. Author, "Title," *Journal*, vol. X,
             no. Y, pp. Z, Year. doi: xxx.
    """
    parts: list[str] = [f"[{number}]"]

    authors = citation.get("authors", [])
    author_str = _format_ieee_authors(authors)
    if author_str:
        parts.append(f"{author_str},")

    title = citation.get("title", "")
    entry_type = citation.get("entry_type", "article")
    if entry_type == "article":
        parts.append(f'"{title},"')
    else:
        parts.append(f"*{title}*,")

    journal = citation.get("journal")
    if journal:
        parts.append(f"*{journal}*,")

    volume = citation.get("volume")
    if volume:
        parts.append(f"vol. {volume},")

    issue = citation.get("issue")
    if issue:
        parts.append(f"no. {issue},")

    pages = citation.get("pages")
    if pages:
        parts.append(f"pp. {pages},")

    year = citation.get("year")
    if year:
        parts.append(f"{year}.")
    else:
        parts.append("n.d.")

    doi = citation.get("doi")
    if doi:
        parts.append(f"doi: {doi}.")

    return " ".join(parts)


def format_ieee_in_text(number: int) -> str:
    """Return an IEEE in-text citation: [N]."""
    return f"[{number}]"


def _format_ieee_authors(authors: list[dict[str, str | None]]) -> str:
    """Format author list for IEEE: A. B. Surname and C. D. Surname."""
    if not authors:
        return ""

    formatted = [_ieee_author_name(a) for a in authors]

    if len(formatted) == 1:
        return formatted[0]

    if len(formatted) == 2:
        return f"{formatted[0]} and {formatted[1]}"

    if len(formatted) <= 6:
        return ", ".join(formatted[:-1]) + f", and {formatted[-1]}"

    return f"{formatted[0]} et al."


def _ieee_author_name(author: dict[str, str | None]) -> str:
    """Format a single author in IEEE style: A. B. Surname."""
    family = author.get("family", "")
    given = author.get("given")
    if not given:
        return family
    initials = _initials(given)
    return f"{initials} {family}"


def _initials(given: str) -> str:
    """Convert given names to IEEE initials: 'Tai Man' -> 'T. M.'"""
    parts = given.replace("-", " ").split()
    return " ".join(f"{p[0].upper()}." for p in parts if p)
