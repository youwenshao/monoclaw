"""LLM-backed translation with language detection heuristics."""

from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger("openclaw.supplier-bot.translator")

CJK_RANGES = (
    "\u4e00-\u9fff"   # CJK Unified Ideographs
    "\u3400-\u4dbf"   # CJK Extension A
    "\uf900-\ufaff"   # CJK Compatibility Ideographs
)
CJK_PATTERN = re.compile(f"[{CJK_RANGES}]")

LANG_NAMES = {
    "en": "English",
    "zh": "Simplified Chinese",
    "zh-tw": "Traditional Chinese",
    "zh-hk": "Traditional Chinese (Hong Kong / Cantonese)",
    "ja": "Japanese",
    "ko": "Korean",
}


class Translator:
    """Translate text between languages using an LLM backend."""

    def __init__(self, llm: Any | None = None) -> None:
        self.llm = llm

    def translate(self, text: str, source_lang: str, target_lang: str) -> str:
        """Translate *text* from *source_lang* to *target_lang*.

        If no LLM is configured the original text is returned unchanged so
        downstream code can still function during development.
        """
        if not text.strip():
            return text

        if source_lang == target_lang:
            return text

        if self.llm is None:
            logger.warning("No LLM configured — returning original text as translation stub")
            return text

        source_name = LANG_NAMES.get(source_lang, source_lang)
        target_name = LANG_NAMES.get(target_lang, target_lang)

        prompt = (
            f"Translate the following text from {source_name} to {target_name}. "
            "Preserve the original meaning, tone, and any technical/trade terminology. "
            "Return ONLY the translated text, nothing else.\n\n"
            f"Text:\n{text}"
        )

        try:
            result = self.llm.generate(prompt)
            translated = result if isinstance(result, str) else str(result)
            logger.info("Translated %d chars %s→%s", len(text), source_lang, target_lang)
            return translated.strip()
        except Exception:
            logger.exception("LLM translation failed — returning original text")
            return text

    def detect_language(self, text: str) -> str:
        """Detect language using a CJK-character heuristic.

        Returns ``"zh"`` when ≥30 % of non-whitespace characters are CJK,
        otherwise ``"en"``.  Good enough for the EN↔CN supplier workflow;
        can be extended with a proper model later.
        """
        if not text.strip():
            return "en"

        non_space = re.sub(r"\s+", "", text)
        if not non_space:
            return "en"

        cjk_count = len(CJK_PATTERN.findall(non_space))
        ratio = cjk_count / len(non_space)
        return "zh" if ratio >= 0.3 else "en"
