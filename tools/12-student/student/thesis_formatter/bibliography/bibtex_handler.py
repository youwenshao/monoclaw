"""Parse BibTeX .bib files into structured reference dictionaries."""

from __future__ import annotations

import re
from pathlib import Path


def parse_bibtex(bib_path: str) -> list[dict]:
    text = Path(bib_path).read_text(encoding="utf-8")
    entries = []

    for match in re.finditer(r"@(\w+)\s*\{([^,]+),\s*(.*?)\n\}", text, re.DOTALL):
        entry_type = match.group(1).lower()
        cite_key = match.group(2).strip()
        body = match.group(3)

        fields = _parse_fields(body)
        fields["entry_type"] = entry_type
        fields["cite_key"] = cite_key
        entries.append(fields)

    return entries


def _parse_fields(body: str) -> dict:
    fields: dict[str, str] = {}
    for match in re.finditer(r"(\w+)\s*=\s*[{\"](.+?)[}\"]", body, re.DOTALL):
        key = match.group(1).lower().strip()
        value = match.group(2).strip()
        value = re.sub(r"\s+", " ", value)
        fields[key] = value
    return fields
