"""Cantonese detection and normalisation utilities."""

from __future__ import annotations

import re

CANTONESE_MARKERS = {
    "嘅", "咗", "嚟", "喺", "俾", "畀", "咁", "嗰", "乜", "冇",
    "嘢", "佢", "咪", "啲", "噉", "嘛", "喇", "啦", "囉", "㗎",
    "嗮", "曬", "唔", "係", "嚿", "揸", "搵", "瞓", "攞", "靚",
}

CANTONESE_CHAR_PATTERN = re.compile(
    "[" + "".join(re.escape(c) for c in CANTONESE_MARKERS) + "]"
)


class CantoneseHandler:
    """Detect Cantonese-specific text and normalise toward Mandarin."""

    @staticmethod
    def detect_cantonese(text: str) -> bool:
        """Return ``True`` if *text* contains Cantonese-specific particles.

        Looks for characters that are distinctive to written Cantonese
        (e.g. 嘅, 咗, 嚟, 喺, 唔, 冇).  If ≥2 markers are found the
        text is considered Cantonese.
        """
        if not text:
            return False
        matches = CANTONESE_CHAR_PATTERN.findall(text)
        return len(matches) >= 2

    @staticmethod
    def normalize_to_mandarin(text: str) -> str:
        """Attempt basic Cantonese → Mandarin normalisation.

        This is a placeholder for future rule-based or ML normalisation.
        Currently returns the text unchanged — the intent is for the LLM
        translator to handle Cantonese input, but calling code can still
        invoke this method as part of its pipeline.
        """
        return text
