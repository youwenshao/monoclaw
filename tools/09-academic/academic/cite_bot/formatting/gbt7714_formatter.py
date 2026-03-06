"""GB/T 7714-2015 Chinese national standard citation formatter."""

from __future__ import annotations

from typing import Any


def format_gbt7714(citation: dict[str, Any], chinese: bool = True) -> str:
    """Format a citation per GB/T 7714-2015.

    When *chinese* is True, use Chinese punctuation (，、：) and the standard
    [序号] Author. Title[J]. Journal, Year, Volume(Issue): Pages. format.
    """
    authors = citation.get("authors", [])
    if chinese:
        author_str = _format_chinese_authors(authors)
    else:
        author_str = _format_english_authors_gbt(authors)

    sep = "．" if chinese else ". "
    colon = "：" if chinese else ": "
    comma = "，" if chinese else ", "

    entry_type = citation.get("entry_type", "article")
    type_code = _type_code(entry_type)

    title = citation.get("title", "")
    year = citation.get("year", "")
    journal = citation.get("journal", "")
    volume = citation.get("volume", "")
    issue = citation.get("issue", "")
    pages = citation.get("pages", "")

    parts: list[str] = []
    if author_str:
        parts.append(author_str)
    parts.append(f"{sep}{title}[{type_code}]")

    if entry_type == "article" and journal:
        parts.append(f"{sep}{journal}")
        if year:
            parts.append(f"{comma}{year}")
        if volume:
            vol_part = volume
            if issue:
                vol_part += f"({issue})"
            parts.append(f"{comma}{vol_part}")
        if pages:
            parts.append(f"{colon}{pages}")
    elif entry_type in ("book", "chapter"):
        publisher = citation.get("publisher", "")
        if publisher:
            parts.append(f"{sep}{publisher}")
        if year:
            parts.append(f"{comma}{year}")
        if pages:
            parts.append(f"{colon}{pages}")
    else:
        if journal:
            parts.append(f"{sep}{journal}")
        if year:
            parts.append(f"{comma}{year}")
        if pages:
            parts.append(f"{colon}{pages}")

    doi = citation.get("doi")
    if doi:
        parts.append(f"{sep}DOI:{doi}")

    text = "".join(parts)
    if not text.endswith("．") and not text.endswith("."):
        text += "．" if chinese else "."
    return text


def _format_chinese_authors(authors: list[dict[str, str | None]]) -> str:
    """Format authors for GB/T 7714 with Chinese name preference.

    Uses name_tc if available, otherwise falls back to FAMILY Given format.
    Up to 3 authors listed; 4+ uses first 3 + ,等.
    """
    if not authors:
        return ""

    names: list[str] = []
    for a in authors:
        name_tc = a.get("name_tc")
        if name_tc:
            names.append(name_tc)
        else:
            family = a.get("family", "")
            given = a.get("given", "")
            if given:
                names.append(f"{family.upper()} {given}")
            else:
                names.append(family.upper())

    if len(names) <= 3:
        return "，".join(names)
    return "，".join(names[:3]) + "，等"


def _format_english_authors_gbt(authors: list[dict[str, str | None]]) -> str:
    """Format authors in GB/T 7714 English style: FAMILY Given Name.

    Up to 3 authors listed; 4+ uses first 3 + , et al.
    """
    if not authors:
        return ""

    names: list[str] = []
    for a in authors:
        family = a.get("family", "")
        given = a.get("given", "")
        if given:
            names.append(f"{family.upper()} {given}")
        else:
            names.append(family.upper())

    if len(names) <= 3:
        return ", ".join(names)
    return ", ".join(names[:3]) + ", et al"


_TYPE_CODES: dict[str, str] = {
    "article": "J",
    "book": "M",
    "chapter": "M",
    "conference": "C",
    "thesis": "D",
    "report": "R",
    "website": "EB/OL",
    "other": "Z",
}


def _type_code(entry_type: str) -> str:
    return _TYPE_CODES.get(entry_type, "Z")
