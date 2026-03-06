"""Traditional/Simplified Chinese conversion using opencc."""

from __future__ import annotations

import opencc


_s2t = opencc.OpenCC("s2t")
_t2s = opencc.OpenCC("t2s")


def to_traditional(text: str) -> str:
    """Convert Simplified Chinese text to Traditional Chinese.

    Args:
        text: Input text (may contain mixed content).

    Returns:
        Text with Simplified characters converted to Traditional.
    """
    return _s2t.convert(text)


def to_simplified(text: str) -> str:
    """Convert Traditional Chinese text to Simplified Chinese.

    Args:
        text: Input text (may contain mixed content).

    Returns:
        Text with Traditional characters converted to Simplified.
    """
    return _t2s.convert(text)


def convert(text: str, target: str) -> str:
    """Convert text to the target Chinese variant.

    Args:
        text: Input text.
        target: Target variant — 'tc' for Traditional, 'sc' for Simplified.

    Returns:
        Converted text.

    Raises:
        ValueError: If target is not 'tc' or 'sc'.
    """
    if target == "tc":
        return to_traditional(text)
    if target == "sc":
        return to_simplified(text)
    raise ValueError(f"target must be 'tc' or 'sc', got {target!r}")


def is_traditional(text: str) -> bool:
    """Detect if text is predominantly Traditional Chinese.

    Converts the text to Simplified and back to Traditional, then compares
    with the original. If they match closely, the text is Traditional.

    Args:
        text: Chinese text to check.

    Returns:
        True if the text appears to be Traditional Chinese.
    """
    if not text or not text.strip():
        return False

    simplified = to_simplified(text)
    back_to_traditional = to_traditional(simplified)

    matches = sum(1 for a, b in zip(text, back_to_traditional) if a == b)
    total = max(len(text), 1)

    return (matches / total) > 0.95
