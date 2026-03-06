"""Chinese word segmentation for glossary matching using jieba."""

from __future__ import annotations

import jieba


def segment_chinese(text: str) -> list[str]:
    """Segment Chinese text into words using jieba.

    Args:
        text: Chinese text to segment.

    Returns:
        List of segmented tokens.
    """
    return list(jieba.cut(text))


def find_glossary_matches(
    text: str,
    glossary_terms: list[dict],
    source_lang: str,
) -> list[dict]:
    """Find which glossary terms appear in the source text.

    Uses jieba segmentation for Chinese and simple substring matching
    for English to identify glossary terms present in the text.

    Args:
        text: Source text to scan.
        glossary_terms: List of glossary term dicts with term_en, term_tc, term_sc.
        source_lang: Source language code ('en', 'tc', 'sc').

    Returns:
        List of matching glossary term dicts with an added 'match_position' key.
    """
    lang_key = {"en": "term_en", "tc": "term_tc", "sc": "term_sc"}
    key = lang_key.get(source_lang, "term_en")

    matches: list[dict] = []

    if source_lang in ("tc", "sc"):
        tokens = segment_chinese(text)
        token_set = set(tokens)
        joined = text

        for term in glossary_terms:
            src_term = term.get(key, "")
            if not src_term:
                continue
            if src_term in token_set or src_term in joined:
                pos = joined.find(src_term)
                match = dict(term)
                match["match_position"] = pos if pos >= 0 else 0
                matches.append(match)
    else:
        text_lower = text.lower()
        for term in glossary_terms:
            src_term = term.get(key, "")
            if not src_term:
                continue
            pos = text_lower.find(src_term.lower())
            if pos >= 0:
                match = dict(term)
                match["match_position"] = pos
                matches.append(match)

    return matches


def add_custom_words(terms: list[str]) -> None:
    """Add custom words to jieba's dictionary for better segmentation.

    Useful for adding domain-specific terminology that jieba might not
    recognise by default.

    Args:
        terms: List of Chinese terms to add to the dictionary.
    """
    for term in terms:
        if term and term.strip():
            jieba.add_word(term.strip())
