"""Full paper translation with citation and figure reference preservation."""

from __future__ import annotations

import re
from typing import Any

from openclaw_shared.database import get_db

from academic.translate_assist.translation.domain_prompter import (
    get_domain_system_prompt,
)
from academic.translate_assist.translation.translator import (
    _build_translation_prompt,
    _estimate_confidence,
)


_CITATION_PATTERN = re.compile(r"\[(\d+(?:\s*[,;]\s*\d+)*)\]")
_FIGURE_PATTERN = re.compile(
    r"(?:Figure|Fig\.|Table|Equation|Eq\.)\s*\d+(?:\.\d+)?(?:\s*[a-zA-Z])?",
    re.IGNORECASE,
)


def _preserve_citations(text: str) -> tuple[str, list[tuple[str, str]]]:
    """Extract citation markers before translation, returning placeholders.

    Args:
        text: Source text containing citation markers like [1], [2,3].

    Returns:
        Tuple of (text_with_placeholders, list_of_(placeholder, original) pairs).
    """
    replacements: list[tuple[str, str]] = []
    counter = 0

    def _replace(m: re.Match[str]) -> str:
        nonlocal counter
        placeholder = f"__CITE_{counter}__"
        replacements.append((placeholder, m.group(0)))
        counter += 1
        return placeholder

    cleaned = _CITATION_PATTERN.sub(_replace, text)
    return cleaned, replacements


def _preserve_figure_refs(text: str) -> tuple[str, list[tuple[str, str]]]:
    """Extract Figure/Table references before translation.

    Args:
        text: Source text containing figure/table references.

    Returns:
        Tuple of (text_with_placeholders, list_of_(placeholder, original) pairs).
    """
    replacements: list[tuple[str, str]] = []
    counter = 0

    def _replace(m: re.Match[str]) -> str:
        nonlocal counter
        placeholder = f"__FIGREF_{counter}__"
        replacements.append((placeholder, m.group(0)))
        counter += 1
        return placeholder

    cleaned = _FIGURE_PATTERN.sub(_replace, text)
    return cleaned, replacements


def _restore_placeholders(text: str, replacements: list[tuple[str, str]]) -> str:
    """Restore original markers from placeholders."""
    result = text
    for placeholder, original in replacements:
        result = result.replace(placeholder, original)
    return result


def translate_paper(
    segments: list[dict],
    source_lang: str,
    target_lang: str,
    domain: str,
    llm: Any,
    db_path: Any,
    project_id: int,
    glossary_terms: list[dict] | None = None,
) -> list[dict]:
    """Translate all segments of a paper sequentially, preserving structure.

    Each segment is translated in order so that the previous translation
    provides coherence context. Results are persisted to the database.

    Args:
        segments: List of dicts with keys segment_index, section_name, source_text.
        source_lang: Source language code ('en', 'tc', 'sc').
        target_lang: Target language code ('en', 'tc', 'sc').
        domain: Academic domain for prompt tuning.
        llm: LLM provider with a `generate(prompt: str) -> str` method.
        db_path: Path to the SQLite database.
        project_id: Translation project ID for DB persistence.
        glossary_terms: Optional glossary terms.

    Returns:
        List of dicts with keys: segment_index, source_text, translated_text, confidence.
    """
    glossary = glossary_terms or []
    system_prompt = get_domain_system_prompt(domain, source_lang, target_lang)
    results: list[dict] = []
    prev_translation = ""

    for seg in segments:
        source_text = seg.get("source_text", "")
        segment_index = seg.get("segment_index", 0)
        section_name = seg.get("section_name", "")

        if not source_text.strip():
            result = {
                "segment_index": segment_index,
                "source_text": source_text,
                "translated_text": "",
                "confidence": 1.0,
            }
            results.append(result)
            _save_segment(db_path, project_id, segment_index, section_name, source_text, "", 1.0)
            continue

        text_no_cites, cite_replacements = _preserve_citations(source_text)
        text_no_refs, fig_replacements = _preserve_figure_refs(text_no_cites)

        prompt = _build_translation_prompt(
            text_no_refs, source_lang, target_lang, glossary, prev_translation
        )
        full_prompt = (
            f"{system_prompt}\n\n"
            f"Section: {section_name}\n\n"
            f"Important: Preserve any placeholders like __CITE_N__ and __FIGREF_N__ exactly as they appear.\n\n"
            f"{prompt}"
        )

        raw = llm.generate(full_prompt)
        translated = raw.strip()

        translated = _restore_placeholders(translated, fig_replacements)
        translated = _restore_placeholders(translated, cite_replacements)

        confidence = _estimate_confidence(source_text, translated, source_lang, target_lang)

        _save_segment(
            db_path, project_id, segment_index, section_name,
            source_text, translated, confidence,
        )

        result = {
            "segment_index": segment_index,
            "source_text": source_text,
            "translated_text": translated,
            "confidence": confidence,
        }
        results.append(result)
        prev_translation = translated

    return results


def _save_segment(
    db_path: Any,
    project_id: int,
    segment_index: int,
    section_name: str,
    source_text: str,
    translated_text: str,
    confidence: float,
) -> None:
    """Persist a translated segment to the database."""
    with get_db(db_path) as conn:
        conn.execute(
            """
            INSERT INTO translation_segments
                (project_id, segment_index, section_name, source_text, translated_text, confidence)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (project_id, segment_index, section_name, source_text, translated_text, confidence),
        )
