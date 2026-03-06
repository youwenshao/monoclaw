"""Format references in standard citation styles (APA, MLA, Chicago, IEEE)."""

from __future__ import annotations


def format_bibliography(references: list[dict], style: str = "apa") -> list[str]:
    formatter = _FORMATTERS.get(style.lower(), _format_apa)
    return [formatter(ref) for ref in references]


def _format_apa(ref: dict) -> str:
    authors = ref.get("author", "Unknown")
    year = ref.get("year", "n.d.")
    title = ref.get("title", "Untitled")
    source = ref.get("journal") or ref.get("booktitle") or ref.get("publisher", "")
    volume = ref.get("volume", "")
    pages = ref.get("pages", "")

    parts = [f"{authors} ({year}). {title}."]
    if source:
        italic_source = source
        if volume:
            italic_source += f", {volume}"
        parts.append(f" {italic_source}")
    if pages:
        parts.append(f", {pages}")
    parts.append(".")
    return "".join(parts)


def _format_mla(ref: dict) -> str:
    authors = ref.get("author", "Unknown")
    title = ref.get("title", "Untitled")
    source = ref.get("journal") or ref.get("booktitle") or ref.get("publisher", "")
    year = ref.get("year", "n.d.")
    pages = ref.get("pages", "")

    parts = [f'{authors}. "{title}."']
    if source:
        parts.append(f" {source}")
    if pages:
        parts.append(f", pp. {pages}")
    parts.append(f", {year}.")
    return "".join(parts)


def _format_chicago(ref: dict) -> str:
    authors = ref.get("author", "Unknown")
    title = ref.get("title", "Untitled")
    source = ref.get("journal") or ref.get("booktitle") or ""
    publisher = ref.get("publisher", "")
    year = ref.get("year", "n.d.")

    parts = [f'{authors}. "{title}."']
    if source:
        parts.append(f" {source}")
    if publisher:
        parts.append(f" {publisher}")
    parts.append(f", {year}.")
    return "".join(parts)


def _format_ieee(ref: dict) -> str:
    authors = ref.get("author", "Unknown")
    title = ref.get("title", "Untitled")
    source = ref.get("journal") or ref.get("booktitle") or ""
    volume = ref.get("volume", "")
    pages = ref.get("pages", "")
    year = ref.get("year", "n.d.")

    parts = [f'{authors}, "{title},"']
    if source:
        parts.append(f" {source}")
    if volume:
        parts.append(f", vol. {volume}")
    if pages:
        parts.append(f", pp. {pages}")
    parts.append(f", {year}.")
    return "".join(parts)


_FORMATTERS = {
    "apa": _format_apa,
    "mla": _format_mla,
    "chicago": _format_chicago,
    "ieee": _format_ieee,
}
