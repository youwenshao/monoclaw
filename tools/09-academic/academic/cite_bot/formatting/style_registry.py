"""Style definitions and dispatch for citation formatting."""

from __future__ import annotations

from typing import Any, Callable

from academic.cite_bot.formatting.apa_formatter import format_apa7
from academic.cite_bot.formatting.harvard_formatter import format_harvard
from academic.cite_bot.formatting.ieee_formatter import format_ieee
from academic.cite_bot.formatting.gbt7714_formatter import format_gbt7714
from academic.cite_bot.formatting.csl_engine import format_with_csl

STYLES: dict[str, str] = {
    "apa7": "APA 7th Edition",
    "harvard": "Harvard",
    "ieee": "IEEE",
    "gbt7714": "GB/T 7714-2015",
    "vancouver": "Vancouver",
    "chicago": "Chicago (Author-Date)",
    "mla9": "MLA 9th Edition",
}

_NATIVE_FORMATTERS: dict[str, Callable[..., str]] = {
    "apa7": format_apa7,
    "harvard": format_harvard,
    "ieee": format_ieee,
    "gbt7714": format_gbt7714,
}


def get_formatter(style: str) -> Callable[..., str]:
    """Return the formatting function for the given style key.

    Native formatters are returned for apa7, harvard, ieee, and gbt7714.
    For other styles (vancouver, chicago, mla9, or any CSL name), returns a
    closure that delegates to the CSL engine.
    """
    if style in _NATIVE_FORMATTERS:
        return _NATIVE_FORMATTERS[style]

    def _csl_formatter(citation: dict[str, Any], **kwargs: Any) -> str:
        return format_with_csl(citation, style)

    return _csl_formatter


def format_citation(citation: dict[str, Any], style: str) -> str:
    """Format a single citation in the requested style."""
    formatter = get_formatter(style)
    return formatter(citation)
