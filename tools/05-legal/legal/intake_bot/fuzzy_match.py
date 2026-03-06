"""Fuzzy name matching with phonetic support for Chinese/English names."""

from __future__ import annotations

import re
import unicodedata


def fuzzy_score(name1: str, name2: str) -> float:
    """Return 0.0–1.0 similarity using Levenshtein distance via rapidfuzz."""
    if not name1 or not name2:
        return 0.0

    n1 = _normalize(name1)
    n2 = _normalize(name2)

    if n1 == n2:
        return 1.0

    try:
        from rapidfuzz import fuzz
        return fuzz.ratio(n1, n2) / 100.0
    except ImportError:
        return _fallback_levenshtein_ratio(n1, n2)


def phonetic_match_score(name1: str, name2: str) -> float:
    """Compare names phonetically — converts Chinese characters to pinyin first.

    Handles Traditional Chinese, Simplified Chinese, and romanized variants.
    Returns 0.0–1.0 similarity.
    """
    if not name1 or not name2:
        return 0.0

    p1 = _to_phonetic(name1)
    p2 = _to_phonetic(name2)

    if p1 == p2:
        return 1.0

    try:
        from rapidfuzz import fuzz
        return fuzz.ratio(p1, p2) / 100.0
    except ImportError:
        return _fallback_levenshtein_ratio(p1, p2)


def combined_match_score(name1: str, name2: str) -> tuple[float, str]:
    """Return (best_score, match_type) across exact, fuzzy, and phonetic methods.

    match_type is one of: "exact", "fuzzy", "phonetic".
    """
    n1 = _normalize(name1)
    n2 = _normalize(name2)

    if n1 == n2:
        return (1.0, "exact")

    f_score = fuzzy_score(name1, name2)
    p_score = phonetic_match_score(name1, name2)

    if p_score > f_score:
        return (p_score, "phonetic")
    return (f_score, "fuzzy")


def validate_hkid_last4(value: str) -> bool:
    """Validate HKID last-4 format: one letter followed by three digits (e.g. A123)."""
    if not value or len(value) != 4:
        return False
    return bool(re.match(r"^[A-Za-z]\d{3}$", value))


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _normalize(name: str) -> str:
    """Lower-case, strip whitespace, normalize unicode."""
    text = unicodedata.normalize("NFC", name.strip().lower())
    text = re.sub(r"\s+", " ", text)
    return text


def _contains_cjk(text: str) -> bool:
    """Check if text contains CJK unified ideographs."""
    for ch in text:
        cp = ord(ch)
        if (0x4E00 <= cp <= 0x9FFF    # CJK Unified Ideographs
            or 0x3400 <= cp <= 0x4DBF  # CJK Unified Ideographs Extension A
            or 0xF900 <= cp <= 0xFAFF  # CJK Compatibility Ideographs
            or 0x20000 <= cp <= 0x2A6DF):
            return True
    return False


def _to_phonetic(name: str) -> str:
    """Convert a name to its phonetic representation.

    Chinese characters -> pinyin (tone-stripped), English -> lowered.
    """
    text = name.strip()
    if not text:
        return ""

    if _contains_cjk(text):
        try:
            from pypinyin import lazy_pinyin, Style
            syllables = lazy_pinyin(text, style=Style.NORMAL)
            return " ".join(syllables).lower()
        except ImportError:
            return _normalize(text)

    return _normalize(text)


def _fallback_levenshtein_ratio(s1: str, s2: str) -> float:
    """Pure-Python Levenshtein ratio when rapidfuzz is unavailable."""
    if not s1 and not s2:
        return 1.0
    if not s1 or not s2:
        return 0.0

    len1, len2 = len(s1), len(s2)

    prev = list(range(len2 + 1))
    curr = [0] * (len2 + 1)

    for i in range(1, len1 + 1):
        curr[0] = i
        for j in range(1, len2 + 1):
            cost = 0 if s1[i - 1] == s2[j - 1] else 1
            curr[j] = min(
                prev[j] + 1,
                curr[j - 1] + 1,
                prev[j - 1] + cost,
            )
        prev, curr = curr, prev

    distance = prev[len2]
    max_len = max(len1, len2)
    return 1.0 - (distance / max_len)
