"""Specialized academic abstract translation preserving structure."""

from __future__ import annotations

import re
from typing import Any

from academic.translate_assist.translation.domain_prompter import (
    get_domain_system_prompt,
)
from academic.translate_assist.translation.translator import _build_translation_prompt


_SECTION_PATTERNS: dict[str, list[re.Pattern[str]]] = {
    "background": [
        re.compile(r"(?i)^(?:background|introduction|context|目的|背景|研究背景)[:\s：]?", re.MULTILINE),
    ],
    "methods": [
        re.compile(r"(?i)^(?:method(?:s|ology)?|design|approach|方法|研究方法)[:\s：]?", re.MULTILINE),
    ],
    "results": [
        re.compile(r"(?i)^(?:results?|findings?|結果|研究結果)[:\s：]?", re.MULTILINE),
    ],
    "conclusion": [
        re.compile(r"(?i)^(?:conclusion(?:s)?|implications?|discussion|結論|總結)[:\s：]?", re.MULTILINE),
    ],
}


def detect_abstract_structure(text: str) -> list[dict]:
    """Identify background/methods/results/conclusion sections in an abstract.

    Args:
        text: Raw abstract text.

    Returns:
        List of dicts with keys: section, start, end, text.
        Falls back to a single 'full' section if no structure is detected.
    """
    matches: list[tuple[str, int]] = []
    for section_name, patterns in _SECTION_PATTERNS.items():
        for pattern in patterns:
            m = pattern.search(text)
            if m:
                matches.append((section_name, m.start()))
                break

    if len(matches) < 2:
        return [{"section": "full", "start": 0, "end": len(text), "text": text.strip()}]

    matches.sort(key=lambda x: x[1])

    sections: list[dict] = []
    for i, (section_name, start) in enumerate(matches):
        end = matches[i + 1][1] if i + 1 < len(matches) else len(text)
        section_text = text[start:end].strip()
        for pattern in _SECTION_PATTERNS[section_name]:
            section_text = pattern.sub("", section_text).strip()
        sections.append({
            "section": section_name,
            "start": start,
            "end": end,
            "text": section_text,
        })

    return sections


def translate_abstract(
    abstract_text: str,
    source_lang: str,
    target_lang: str,
    domain: str,
    llm: Any,
    glossary_terms: list[dict] | None = None,
) -> dict:
    """Translate an academic abstract preserving its structure.

    Args:
        abstract_text: Full abstract text.
        source_lang: Source language code ('en', 'tc', 'sc').
        target_lang: Target language code ('en', 'tc', 'sc').
        domain: Academic domain for prompt tuning.
        llm: LLM provider with a `generate(prompt: str) -> str` method.
        glossary_terms: Optional glossary terms.

    Returns:
        Dict with keys: translated_text, confidence, sections_detected.
    """
    if not abstract_text or not abstract_text.strip():
        return {"translated_text": "", "confidence": 1.0, "sections_detected": []}

    glossary = glossary_terms or []
    sections = detect_abstract_structure(abstract_text)
    section_names = [s["section"] for s in sections]

    system_prompt = get_domain_system_prompt(domain, source_lang, target_lang)

    if len(sections) == 1 and sections[0]["section"] == "full":
        prompt = _build_translation_prompt(
            abstract_text, source_lang, target_lang, glossary, ""
        )
        full_prompt = (
            f"{system_prompt}\n\n"
            f"This is an academic abstract. Translate it as a cohesive unit.\n\n"
            f"{prompt}"
        )
        raw = llm.generate(full_prompt)
        translated = raw.strip()
        confidence = _abstract_confidence(abstract_text, translated, source_lang, target_lang)
        return {
            "translated_text": translated,
            "confidence": confidence,
            "sections_detected": section_names,
        }

    translated_parts: list[str] = []
    confidences: list[float] = []
    prev = ""

    for section in sections:
        section_label = section["section"].capitalize()
        prompt = _build_translation_prompt(
            section["text"], source_lang, target_lang, glossary, prev
        )
        full_prompt = (
            f"{system_prompt}\n\n"
            f"This is the '{section_label}' section of an academic abstract. "
            f"Translate preserving its role in the abstract structure.\n\n"
            f"{prompt}"
        )
        raw = llm.generate(full_prompt)
        section_translated = raw.strip()

        section_header_map = {
            "background": {"en": "Background:", "tc": "背景：", "sc": "背景："},
            "methods": {"en": "Methods:", "tc": "方法：", "sc": "方法："},
            "results": {"en": "Results:", "tc": "結果：", "sc": "结果："},
            "conclusion": {"en": "Conclusion:", "tc": "結論：", "sc": "结论："},
        }
        header = section_header_map.get(section["section"], {}).get(target_lang, "")
        if header:
            translated_parts.append(f"{header} {section_translated}")
        else:
            translated_parts.append(section_translated)

        conf = _abstract_confidence(section["text"], section_translated, source_lang, target_lang)
        confidences.append(conf)
        prev = section_translated

    combined = "\n\n".join(translated_parts)
    avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0

    return {
        "translated_text": combined,
        "confidence": round(avg_confidence, 2),
        "sections_detected": section_names,
    }


def _abstract_confidence(
    source: str, translated: str, source_lang: str, target_lang: str
) -> float:
    """Heuristic confidence for abstract translation quality."""
    if not translated:
        return 0.0

    score = 0.85
    source_len = len(source)
    trans_len = len(translated)

    if source_len > 0:
        ratio = trans_len / source_len
        if source_lang == "en" and target_lang in ("tc", "sc"):
            if 0.25 <= ratio <= 0.85:
                score += 0.05
        elif source_lang in ("tc", "sc") and target_lang == "en":
            if 1.2 <= ratio <= 4.0:
                score += 0.05

    if trans_len < 20:
        score -= 0.15

    return max(0.0, min(1.0, round(score, 2)))
