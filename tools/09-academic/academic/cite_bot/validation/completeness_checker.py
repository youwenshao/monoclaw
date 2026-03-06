"""Check citations for missing required fields per style and entry type."""

from __future__ import annotations

from typing import Any

REQUIRED_FIELDS: dict[str, dict[str, list[str]]] = {
    "article": {
        "apa7": ["authors", "year", "title", "journal", "volume", "pages"],
        "harvard": ["authors", "year", "title", "journal", "volume", "pages"],
        "ieee": ["authors", "title", "journal", "volume", "year"],
        "gbt7714": ["authors", "title", "journal", "year", "volume"],
        "vancouver": ["authors", "title", "journal", "year", "volume", "pages"],
        "chicago": ["authors", "year", "title", "journal", "volume", "pages"],
        "mla9": ["authors", "title", "journal", "volume", "issue", "year", "pages"],
    },
    "book": {
        "apa7": ["authors", "year", "title", "publisher"],
        "harvard": ["authors", "year", "title", "publisher"],
        "ieee": ["authors", "title", "publisher", "year"],
        "gbt7714": ["authors", "title", "publisher", "year"],
        "vancouver": ["authors", "title", "publisher", "year"],
        "chicago": ["authors", "year", "title", "publisher"],
        "mla9": ["authors", "title", "publisher", "year"],
    },
    "chapter": {
        "apa7": ["authors", "year", "title", "journal", "publisher", "pages"],
        "harvard": ["authors", "year", "title", "journal", "publisher", "pages"],
        "ieee": ["authors", "title", "journal", "publisher", "year", "pages"],
        "gbt7714": ["authors", "title", "journal", "publisher", "year", "pages"],
        "vancouver": ["authors", "title", "journal", "publisher", "year", "pages"],
        "chicago": ["authors", "year", "title", "journal", "publisher", "pages"],
        "mla9": ["authors", "title", "journal", "publisher", "year", "pages"],
    },
    "conference": {
        "apa7": ["authors", "year", "title", "journal"],
        "harvard": ["authors", "year", "title", "journal"],
        "ieee": ["authors", "title", "journal", "year"],
        "gbt7714": ["authors", "title", "journal", "year"],
        "vancouver": ["authors", "title", "journal", "year"],
        "chicago": ["authors", "year", "title", "journal"],
        "mla9": ["authors", "title", "journal", "year"],
    },
    "thesis": {
        "apa7": ["authors", "year", "title"],
        "harvard": ["authors", "year", "title"],
        "ieee": ["authors", "title", "year"],
        "gbt7714": ["authors", "title", "year"],
        "vancouver": ["authors", "title", "year"],
        "chicago": ["authors", "year", "title"],
        "mla9": ["authors", "title", "year"],
    },
    "report": {
        "apa7": ["authors", "year", "title"],
        "harvard": ["authors", "year", "title"],
        "ieee": ["authors", "title", "year"],
        "gbt7714": ["authors", "title", "year"],
        "vancouver": ["authors", "title", "year"],
        "chicago": ["authors", "year", "title"],
        "mla9": ["authors", "title", "year"],
    },
    "website": {
        "apa7": ["title", "url"],
        "harvard": ["title", "url"],
        "ieee": ["title", "url"],
        "gbt7714": ["title", "url"],
        "vancouver": ["title", "url"],
        "chicago": ["title", "url"],
        "mla9": ["title", "url"],
    },
    "other": {
        "apa7": ["title"],
        "harvard": ["title"],
        "ieee": ["title"],
        "gbt7714": ["title"],
        "vancouver": ["title"],
        "chicago": ["title"],
        "mla9": ["title"],
    },
}

_WARNINGS_MAP: dict[str, str] = {
    "doi": "No DOI — consider adding one for reliable cross-referencing",
    "issue": "Issue number missing — some styles require it",
    "url": "No URL provided",
    "volume": "Volume number missing",
    "pages": "Page range missing",
    "publisher": "Publisher not specified",
}


def check_completeness(citation: dict[str, Any], style: str = "apa7") -> dict[str, Any]:
    """Check a citation dict for missing required fields.

    Returns: {complete: bool, missing_fields: list[str], warnings: list[str]}
    """
    entry_type = citation.get("entry_type", "article")
    type_reqs = REQUIRED_FIELDS.get(entry_type, REQUIRED_FIELDS.get("other", {}))
    required = type_reqs.get(style, type_reqs.get("apa7", ["title"]))

    missing: list[str] = []
    for field in required:
        value = citation.get(field)
        if value is None:
            missing.append(field)
        elif isinstance(value, str) and not value.strip():
            missing.append(field)
        elif isinstance(value, list) and len(value) == 0:
            missing.append(field)

    warnings: list[str] = []
    optional_checks = ["doi", "issue", "url"]
    if entry_type in ("book", "chapter", "report"):
        optional_checks.append("publisher")

    for field in optional_checks:
        if field in missing or field in required:
            continue
        value = citation.get(field)
        is_empty = value is None or (isinstance(value, str) and not value.strip())
        if is_empty and field in _WARNINGS_MAP:
            warnings.append(_WARNINGS_MAP[field])

    return {
        "complete": len(missing) == 0,
        "missing_fields": missing,
        "warnings": warnings,
    }
