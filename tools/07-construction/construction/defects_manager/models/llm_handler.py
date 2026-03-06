"""LLM wrapper for defect classification tasks."""

from __future__ import annotations

import logging

from openclaw_shared.llm import LLMProvider

from construction.defects_manager.models.prompts import (
    DEFECT_CATEGORIES,
    DEFECT_CLASSIFICATION_PROMPT,
    format_classification_prompt,
)

logger = logging.getLogger("openclaw.construction.defects_manager.llm")


class DefectLLM:
    """Thin wrapper around :class:`LLMProvider` for defect-specific tasks."""

    def __init__(self, provider: LLMProvider) -> None:
        self._llm = provider

    async def classify(self, description: str) -> str:
        """Return the defect category for *description*.

        Falls back to ``"other"`` when the model returns an unrecognised label.
        """
        try:
            raw = await self._llm.generate(
                format_classification_prompt(description),
                system=DEFECT_CLASSIFICATION_PROMPT,
                max_tokens=32,
                temperature=0.1,
            )
            category = raw.strip().lower().replace(" ", "_")
            if category in DEFECT_CATEGORIES:
                return category
            logger.warning("LLM returned unknown category %r — falling back to 'other'", raw.strip())
            return "other"
        except Exception:
            logger.exception("LLM classification failed")
            return "other"
