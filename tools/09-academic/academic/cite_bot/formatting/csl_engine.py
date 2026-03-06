"""Generic CSL formatting engine using citeproc-py with fallback."""

from __future__ import annotations

import json
from typing import Any

try:
    from citeproc import CitationStylesStyle, CitationStylesBibliography, Citation, CitationItem
    from citeproc.source.json import CiteProcJSON
    _HAS_CITEPROC = True
except ImportError:
    _HAS_CITEPROC = False

_CSL_STYLE_MAP: dict[str, str] = {
    "apa7": "apa",
    "harvard": "harvard-cite-them-right",
    "ieee": "ieee",
    "vancouver": "vancouver",
    "chicago": "chicago-author-date",
    "mla9": "modern-language-association",
}


def format_with_csl(citation: dict[str, Any], style_name: str) -> str:
    """Format a citation using a CSL style definition via citeproc-py.

    Falls back to a basic formatting when citeproc-py is unavailable or when
    the requested CSL style file cannot be loaded.
    """
    if not _HAS_CITEPROC:
        return _fallback_format(citation, style_name)

    try:
        csl_name = _CSL_STYLE_MAP.get(style_name, style_name)
        return _citeproc_format(citation, csl_name)
    except Exception:
        return _fallback_format(citation, style_name)


def _citeproc_format(citation: dict[str, Any], csl_name: str) -> str:
    """Run the citeproc-py pipeline for a single citation."""
    csl_item = _to_csl_json(citation)
    source = CiteProcJSON([csl_item])

    try:
        style = CitationStylesStyle(csl_name, validate=False)
    except Exception:
        import importlib.resources as pkg_resources
        style_path = None
        try:
            csl_data = pkg_resources.files("citeproc.data")
            for candidate in (f"{csl_name}.csl", f"styles/{csl_name}.csl"):
                ref = csl_data.joinpath(candidate)
                if ref.is_file():
                    style_path = str(ref)
                    break
        except Exception:
            pass

        if style_path:
            style = CitationStylesStyle(style_path, validate=False)
        else:
            raise

    bib = CitationStylesBibliography(style, source)
    cit = Citation([CitationItem(csl_item["id"])])
    bib.register(cit)

    rendered = bib.bibliography()
    if rendered:
        return str(rendered[0]).strip()
    return _fallback_format(citation, csl_name)


def _to_csl_json(citation: dict[str, Any]) -> dict[str, Any]:
    """Convert our internal citation dict to CSL-JSON format."""
    csl_type_map = {
        "article": "article-journal",
        "book": "book",
        "chapter": "chapter",
        "conference": "paper-conference",
        "thesis": "thesis",
        "report": "report",
        "website": "webpage",
        "other": "article",
    }

    entry_type = citation.get("entry_type", "article")
    csl_type = csl_type_map.get(entry_type, "article")

    csl_authors: list[dict[str, str]] = []
    for a in citation.get("authors", []):
        author_entry: dict[str, str] = {}
        if a.get("family"):
            author_entry["family"] = a["family"]
        if a.get("given"):
            author_entry["given"] = a["given"]
        if author_entry:
            csl_authors.append(author_entry)

    item: dict[str, Any] = {
        "id": citation.get("doi") or citation.get("title", "unknown"),
        "type": csl_type,
        "title": citation.get("title", ""),
        "author": csl_authors,
    }

    year = citation.get("year")
    if year:
        item["issued"] = {"date-parts": [[int(year)]]}

    journal = citation.get("journal")
    if journal:
        item["container-title"] = journal

    for field in ("volume", "issue", "page", "publisher", "DOI", "URL"):
        src_key = field.lower()
        if src_key == "page":
            src_key = "pages"
        if src_key == "doi":
            src_key = "doi"
        val = citation.get(src_key)
        if val:
            item[field] = val

    return item


def _fallback_format(citation: dict[str, Any], style_name: str) -> str:
    """Minimal text fallback when citeproc-py is unavailable."""
    authors = citation.get("authors", [])
    if authors:
        names = ", ".join(a.get("family", "") for a in authors[:3])
        if len(authors) > 3:
            names += " et al."
    else:
        names = ""

    title = citation.get("title", "Untitled")
    year = citation.get("year", "n.d.")
    journal = citation.get("journal", "")
    doi = citation.get("doi", "")

    parts = [names, f"({year})", title]
    if journal:
        parts.append(journal)
    if doi:
        parts.append(f"doi:{doi}")

    return ". ".join(p for p in parts if p) + "."
