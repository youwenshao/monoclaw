"""Entity extraction from consultation text using LLM."""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from openclaw_shared.llm.base import LLMProvider

logger = logging.getLogger("openclaw.scribe-ai.entity")

EXTRACTION_SYSTEM_PROMPT = """\
You are a clinical entity extraction system for a Hong Kong medical/dental clinic.
Extract structured medical entities from consultation text.

Return ONLY valid JSON with these keys:
- medications: array of objects with keys {name, dosage, frequency}
- diagnoses: array of strings
- procedures: array of strings
- follow_up: string or null

Rules:
- Use generic drug names where possible.
- Dosages in metric units.
- Do not wrap in markdown code fences.
"""

EXTRACTION_USER_TEMPLATE = """\
Consultation text:
---
{text}
---

Extract entities as JSON with keys: medications, diagnoses, procedures, follow_up.
"""


class EntityExtractor:
    """Extract structured medical entities from free-text consultation notes."""

    async def extract(
        self,
        text: str,
        llm_provider: LLMProvider,
    ) -> dict[str, Any]:
        """Extract medications, diagnoses, procedures, and follow-up from text."""
        try:
            result = await self._extract_with_llm(text, llm_provider)
            if self._validate(result):
                return self._normalize(result)
            logger.warning("LLM returned invalid entity structure — returning empty")
        except Exception:
            logger.warning("Entity extraction failed", exc_info=True)

        return self._empty_result()

    async def _extract_with_llm(
        self,
        text: str,
        llm: LLMProvider,
    ) -> dict[str, Any]:
        prompt = EXTRACTION_USER_TEMPLATE.format(text=text)
        raw = await llm.generate(
            prompt,
            system=EXTRACTION_SYSTEM_PROMPT,
            max_tokens=1024,
            temperature=0.2,
        )
        return self._parse_json_response(raw)

    @staticmethod
    def _parse_json_response(raw: str) -> dict[str, Any]:
        cleaned = raw.strip()
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
        return json.loads(cleaned)

    @staticmethod
    def _validate(data: Any) -> bool:
        if not isinstance(data, dict):
            return False
        if "medications" not in data or not isinstance(data["medications"], list):
            return False
        if "diagnoses" not in data or not isinstance(data["diagnoses"], list):
            return False
        return True

    @staticmethod
    def _normalize(data: dict[str, Any]) -> dict[str, Any]:
        medications = []
        for med in data.get("medications", []):
            if isinstance(med, dict):
                medications.append({
                    "name": med.get("name", ""),
                    "dosage": med.get("dosage", ""),
                    "frequency": med.get("frequency", ""),
                })
            elif isinstance(med, str):
                medications.append({"name": med, "dosage": "", "frequency": ""})

        return {
            "medications": medications,
            "diagnoses": [str(d) for d in data.get("diagnoses", [])],
            "procedures": [str(p) for p in data.get("procedures", [])],
            "follow_up": data.get("follow_up"),
        }

    @staticmethod
    def _empty_result() -> dict[str, Any]:
        return {
            "medications": [],
            "diagnoses": [],
            "procedures": [],
            "follow_up": None,
        }
