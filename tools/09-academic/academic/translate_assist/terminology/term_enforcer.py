"""Post-translation terminology consistency enforcement."""

from __future__ import annotations

import re


def find_term_violations(
    text: str,
    glossary_terms: list[dict],
    lang: str,
) -> list[dict]:
    """Identify where glossary terms are used inconsistently in translated text.

    Checks whether the text contains source-language terms that should have
    been translated, or uses variant translations instead of the glossary-preferred form.

    Args:
        text: Translated text to check.
        glossary_terms: Glossary term dicts with keys term_en, term_tc, term_sc.
        lang: Target language code ('en', 'tc', 'sc') — the language of `text`.

    Returns:
        List of violation dicts with keys: term_id, expected, found, position, violation_type.
    """
    lang_key = {"en": "term_en", "tc": "term_tc", "sc": "term_sc"}
    target_key = lang_key.get(lang, "term_en")

    source_keys = [k for k in lang_key.values() if k != target_key]

    violations: list[dict] = []

    for term in glossary_terms:
        expected = term.get(target_key, "")
        if not expected:
            continue

        term_id = term.get("id", None)

        for src_key in source_keys:
            src_term = term.get(src_key, "")
            if not src_term or src_term == expected:
                continue
            pattern = re.compile(re.escape(src_term), re.IGNORECASE)
            for m in pattern.finditer(text):
                violations.append({
                    "term_id": term_id,
                    "expected": expected,
                    "found": m.group(0),
                    "position": m.start(),
                    "violation_type": "untranslated",
                })

    return violations


def enforce_terminology(
    translated_text: str,
    glossary_terms: list[dict],
    target_lang: str,
) -> tuple[str, list[dict]]:
    """Check translation for inconsistent term usage and apply corrections.

    Replaces untranslated source-language terms with their glossary equivalents.

    Args:
        translated_text: The translated text to check and correct.
        glossary_terms: Glossary term dicts.
        target_lang: Target language code ('en', 'tc', 'sc').

    Returns:
        Tuple of (corrected_text, list of changes_made dicts).
    """
    violations = find_term_violations(translated_text, glossary_terms, target_lang)

    if not violations:
        return translated_text, []

    sorted_violations = sorted(violations, key=lambda v: v["position"], reverse=True)

    corrected = translated_text
    changes: list[dict] = []
    applied_positions: set[int] = set()

    for v in sorted_violations:
        if v["position"] in applied_positions:
            continue

        found = v["found"]
        expected = v["expected"]
        pos = v["position"]

        before = corrected[:pos]
        after = corrected[pos + len(found):]
        corrected = before + expected + after

        changes.append({
            "term_id": v["term_id"],
            "original": found,
            "replacement": expected,
            "position": pos,
            "violation_type": v["violation_type"],
        })
        applied_positions.add(pos)

    return corrected, changes
