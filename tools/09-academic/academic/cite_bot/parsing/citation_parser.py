"""Parse unstructured citation text into structured fields using LLM or heuristics."""

from __future__ import annotations

import json
import re
from typing import Any

_LLM_PROMPT = """\
Extract structured citation metadata from the following raw citation text.
Return ONLY a JSON object with these keys (use null for missing fields):
- title (string)
- authors (list of objects with keys: family, given, name_tc — name_tc is null if unknown)
- year (integer)
- journal (string)
- volume (string)
- issue (string)
- pages (string, e.g. "12-34")
- doi (string, without https://doi.org/ prefix)
- entry_type (one of: article, book, chapter, conference, thesis, report, website, other)

Raw citation text:
{raw_text}
"""


async def parse_citation_text(raw_text: str, llm: Any) -> dict[str, Any]:
    """Send raw citation text to the LLM and parse the structured JSON response."""
    prompt = _LLM_PROMPT.format(raw_text=raw_text.strip())
    response = await llm.generate(prompt)

    cleaned = response.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if match:
            data = json.loads(match.group())
        else:
            return parse_citation_text_heuristic(raw_text)

    return _normalise(data)


def parse_citation_text_heuristic(raw_text: str) -> dict[str, Any]:
    """Regex-based fallback parser for common APA / numbered citation formats."""
    result: dict[str, Any] = {
        "title": None,
        "authors": [],
        "year": None,
        "journal": None,
        "volume": None,
        "issue": None,
        "pages": None,
        "doi": None,
        "entry_type": "article",
    }

    text = raw_text.strip()
    text = re.sub(r"^\[\d+\]\s*", "", text)
    text = re.sub(r"^\d+\.\s*", "", text)

    year_match = re.search(r"\((\d{4})\)", text)
    if year_match:
        result["year"] = int(year_match.group(1))
        author_part = text[: year_match.start()].strip().rstrip(",").strip()
        rest = text[year_match.end() :].strip().lstrip(".").strip()
    else:
        year_match = re.search(r",?\s*(\d{4})\b", text)
        if year_match:
            result["year"] = int(year_match.group(1))
            author_part = text[: year_match.start()].strip().rstrip(",").strip()
            rest = text[year_match.end() :].strip().lstrip(".").strip()
        else:
            author_part = ""
            rest = text

    if author_part:
        result["authors"] = _parse_author_string(author_part)

    title_match = re.match(r"(.+?)\.\s*", rest)
    if title_match:
        result["title"] = title_match.group(1).strip()
        rest = rest[title_match.end() :]
    elif rest:
        result["title"] = rest.rstrip(".")
        rest = ""

    journal_match = re.search(
        r"([A-Z][^,]+?),?\s*(\d+)\s*\((\d+)\)\s*,?\s*([\d\-–]+)", rest
    )
    if journal_match:
        result["journal"] = journal_match.group(1).strip().strip("_").strip("*")
        result["volume"] = journal_match.group(2)
        result["issue"] = journal_match.group(3)
        result["pages"] = journal_match.group(4).replace("–", "-")
    else:
        journal_match2 = re.search(r"([A-Z][^,]+?),?\s*(\d+)\s*,?\s*([\d\-–]+)", rest)
        if journal_match2:
            result["journal"] = journal_match2.group(1).strip().strip("_").strip("*")
            result["volume"] = journal_match2.group(2)
            result["pages"] = journal_match2.group(3).replace("–", "-")

    doi_match = re.search(r"(?:https?://doi\.org/|doi:\s*)(10\.\d{4,}/\S+)", text, re.IGNORECASE)
    if doi_match:
        result["doi"] = doi_match.group(1).rstrip(".")

    return result


def _parse_author_string(author_str: str) -> list[dict[str, str | None]]:
    """Split an author string into structured author dicts."""
    authors: list[dict[str, str | None]] = []
    author_str = re.sub(r"\bet\s+al\.?", "", author_str).strip().rstrip(",").rstrip("&").strip()

    parts = re.split(r"\s*[,;&]\s*(?:and\s+)?|\s+and\s+", author_str)
    parts = [p.strip() for p in parts if p.strip()]

    i = 0
    while i < len(parts):
        part = parts[i]
        if re.match(r"^[A-Z]\.\s*[A-Z]?\.?$", part) and i > 0:
            i += 1
            continue

        if re.match(r"^[A-Z]\.$", part) and i > 0:
            i += 1
            continue

        family, given = _split_name(part)
        if i + 1 < len(parts) and re.match(r"^[A-Z]\.\s*[A-Z]?\.?$", parts[i + 1]):
            given = parts[i + 1]
            i += 1

        name_tc = None
        if re.search(r"[\u4e00-\u9fff]", part):
            name_tc = re.search(r"[\u4e00-\u9fff]+", part)
            name_tc = name_tc.group() if name_tc else None

        authors.append({"family": family, "given": given, "name_tc": name_tc})
        i += 1

    return authors


def _split_name(name: str) -> tuple[str, str | None]:
    """Split a single name string into (family, given)."""
    name = name.strip()
    if "," in name:
        parts = name.split(",", 1)
        return parts[0].strip(), parts[1].strip() or None
    tokens = name.split()
    if len(tokens) == 1:
        return tokens[0], None
    return tokens[-1], " ".join(tokens[:-1])


def _normalise(data: dict[str, Any]) -> dict[str, Any]:
    """Ensure the parsed dict has all expected keys with correct types."""
    defaults: dict[str, Any] = {
        "title": None,
        "authors": [],
        "year": None,
        "journal": None,
        "volume": None,
        "issue": None,
        "pages": None,
        "doi": None,
        "entry_type": "article",
    }
    for key, default in defaults.items():
        if key not in data or data[key] is None:
            data[key] = default

    if isinstance(data.get("year"), str) and data["year"].isdigit():
        data["year"] = int(data["year"])

    if isinstance(data.get("authors"), list):
        normalised: list[dict[str, str | None]] = []
        for a in data["authors"]:
            if isinstance(a, str):
                fam, giv = _split_name(a)
                normalised.append({"family": fam, "given": giv, "name_tc": None})
            elif isinstance(a, dict):
                normalised.append({
                    "family": a.get("family", ""),
                    "given": a.get("given"),
                    "name_tc": a.get("name_tc"),
                })
        data["authors"] = normalised

    return data
