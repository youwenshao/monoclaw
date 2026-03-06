"""Core translation engine using LLM with glossary context."""

from __future__ import annotations

import json
import re
from typing import Any


def _build_translation_prompt(
    text: str,
    source_lang: str,
    target_lang: str,
    glossary: list[dict],
    prev: str,
) -> str:
    """Construct the LLM prompt with domain glossary and context.

    Args:
        text: Source text to translate.
        source_lang: Source language code ('en', 'tc', 'sc').
        target_lang: Target language code ('en', 'tc', 'sc').
        glossary: List of glossary term dicts with keys term_en, term_tc, term_sc.
        prev: Previous paragraph's translation for coherence.

    Returns:
        Formatted prompt string.
    """
    lang_key = {"en": "term_en", "tc": "term_tc", "sc": "term_sc"}
    src_key = lang_key.get(source_lang, "term_en")
    tgt_key = lang_key.get(target_lang, "term_en")

    parts: list[str] = []

    if glossary:
        term_lines = []
        for g in glossary:
            src_term = g.get(src_key, "")
            tgt_term = g.get(tgt_key, "")
            if src_term and tgt_term:
                term_lines.append(f"  {src_term} → {tgt_term}")
        if term_lines:
            parts.append(
                "Use the following glossary for consistent terminology:\n"
                + "\n".join(term_lines)
            )

    if prev:
        parts.append(
            "For coherence, here is the translation of the previous paragraph:\n"
            f"---\n{prev}\n---"
        )

    parts.append(f"Translate the following text:\n\n{text}")

    return "\n\n".join(parts)


def translate_paragraph(
    text: str,
    source_lang: str,
    target_lang: str,
    llm: Any,
    glossary_terms: list[dict] | None = None,
    previous_translation: str = "",
) -> dict:
    """Translate a single paragraph using the LLM with glossary context.

    Args:
        text: Source text to translate.
        source_lang: Source language code ('en', 'tc', 'sc').
        target_lang: Target language code ('en', 'tc', 'sc').
        llm: LLM provider with a `generate(prompt: str) -> str` method.
        glossary_terms: Optional glossary terms for consistent terminology.
        previous_translation: Previous paragraph's translation for coherence.

    Returns:
        Dict with keys: translated_text, confidence, terms_used.
    """
    from academic.translate_assist.translation.domain_prompter import (
        get_domain_system_prompt,
    )

    if not text or not text.strip():
        return {"translated_text": "", "confidence": 1.0, "terms_used": []}

    glossary = glossary_terms or []
    prompt = _build_translation_prompt(text, source_lang, target_lang, glossary, previous_translation)

    system_prompt = get_domain_system_prompt("general", source_lang, target_lang)
    full_prompt = f"{system_prompt}\n\n{prompt}"

    raw_output = llm.generate(full_prompt)
    translated = raw_output.strip()

    lang_key = {"en": "term_en", "tc": "term_tc", "sc": "term_sc"}
    tgt_key = lang_key.get(target_lang, "term_en")
    terms_used = []
    for g in glossary:
        tgt_term = g.get(tgt_key, "")
        if tgt_term and tgt_term in translated:
            terms_used.append(g)

    confidence = _estimate_confidence(text, translated, source_lang, target_lang)

    return {
        "translated_text": translated,
        "confidence": confidence,
        "terms_used": terms_used,
    }


def _estimate_confidence(
    source: str, translated: str, source_lang: str, target_lang: str
) -> float:
    """Heuristic confidence score based on translation characteristics."""
    if not translated:
        return 0.0

    score = 0.85

    source_len = len(source)
    trans_len = len(translated)
    if source_len > 0:
        ratio = trans_len / source_len
        if source_lang == "en" and target_lang in ("tc", "sc"):
            if 0.3 <= ratio <= 0.9:
                score += 0.05
        elif source_lang in ("tc", "sc") and target_lang == "en":
            if 1.2 <= ratio <= 3.5:
                score += 0.05
        else:
            if 0.5 <= ratio <= 2.0:
                score += 0.05

    untranslated_markers = re.findall(r"\[UNTRANSLATED:.*?\]", translated)
    score -= 0.1 * len(untranslated_markers)

    return max(0.0, min(1.0, round(score, 2)))
