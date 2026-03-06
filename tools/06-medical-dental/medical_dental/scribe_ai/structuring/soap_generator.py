"""SOAP note generator using LLM with heuristic fallback."""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from openclaw_shared.llm.base import LLMProvider

logger = logging.getLogger("openclaw.scribe-ai.soap")

SOAP_SYSTEM_PROMPT = """\
You are a medical documentation assistant for a Hong Kong clinic.
Given a consultation transcription, produce a SOAP note.

Rules:
- Use metric units (°C, mmHg, kg, cm, mmol/L).
- Keep language professional and concise.
- Use standard medical abbreviations where appropriate (BP, HR, RR, SpO2, BMI).
- Return ONLY valid JSON with keys: subjective, objective, assessment, plan.
- Each value is a string paragraph.
- Do not wrap in markdown code fences.
"""

SOAP_USER_TEMPLATE = """\
Transcription:
---
{text}
---

Generate the SOAP note as JSON with keys: subjective, objective, assessment, plan.
"""


class SoapGenerator:
    """Generate structured SOAP notes from consultation transcriptions."""

    async def generate(
        self,
        transcription_text: str,
        llm_provider: LLMProvider,
    ) -> dict[str, str]:
        """Generate a SOAP note dict from transcription text.

        Attempts LLM-based generation first, falling back to heuristic
        segmentation if the LLM is unavailable or returns invalid output.
        """
        try:
            result = await self._generate_with_llm(transcription_text, llm_provider)
            if self._validate_soap(result):
                return result
            logger.warning("LLM returned invalid SOAP structure — falling back to heuristic")
        except Exception:
            logger.warning("LLM generation failed — falling back to heuristic", exc_info=True)

        return self._heuristic_segment(transcription_text)

    async def _generate_with_llm(
        self,
        text: str,
        llm: LLMProvider,
    ) -> dict[str, str]:
        prompt = SOAP_USER_TEMPLATE.format(text=text)
        raw = await llm.generate(
            prompt,
            system=SOAP_SYSTEM_PROMPT,
            max_tokens=1024,
            temperature=0.3,
        )
        return self._parse_json_response(raw)

    @staticmethod
    def _parse_json_response(raw: str) -> dict[str, str]:
        cleaned = raw.strip()
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
        return json.loads(cleaned)

    @staticmethod
    def _validate_soap(data: Any) -> bool:
        if not isinstance(data, dict):
            return False
        required = {"subjective", "objective", "assessment", "plan"}
        return required.issubset(data.keys()) and all(
            isinstance(data[k], str) for k in required
        )

    @staticmethod
    def _heuristic_segment(text: str) -> dict[str, str]:
        """Split transcription into SOAP sections using keyword matching."""
        lines = text.strip().splitlines()
        sections: dict[str, list[str]] = {
            "subjective": [],
            "objective": [],
            "assessment": [],
            "plan": [],
        }

        subjective_kw = {"complain", "pain", "feel", "symptom", "history", "onset", "day", "week", "month", "ago"}
        objective_kw = {"bp", "blood pressure", "temp", "temperature", "heart rate", "hr", "bmi", "weight", "exam", "lung", "clear", "mmhg", "°c"}
        assessment_kw = {"diagnos", "impression", "assessment", "likely", "suspect"}
        plan_kw = {"prescri", "plan", "follow", "review", "refer", "advis", "counsel", "return"}

        current_section = "subjective"

        for line in lines:
            lower = line.lower().strip()
            if not lower:
                continue

            if any(kw in lower for kw in plan_kw):
                current_section = "plan"
            elif any(kw in lower for kw in assessment_kw):
                current_section = "assessment"
            elif any(kw in lower for kw in objective_kw):
                current_section = "objective"
            elif any(kw in lower for kw in subjective_kw):
                current_section = "subjective"

            sections[current_section].append(line.strip())

        return {k: " ".join(v) if v else "" for k, v in sections.items()}
