"""Refactoring suggestion engine using LLM analysis."""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any

import yaml

from openclaw_shared.database import get_db
from openclaw_shared.llm.base import LLMProvider

logger = logging.getLogger("vibe-coder.code_qwen.refactorer")

PROMPTS_PATH = Path(__file__).resolve().parent.parent / "prompts" / "system_prompts.yaml"


def _load_system_prompt() -> str:
    with open(PROMPTS_PATH) as f:
        prompts = yaml.safe_load(f)
    return prompts["refactoring"]


class RefactoringEngine:
    """Analyses code and returns structured refactoring suggestions."""

    def __init__(self, llm: LLMProvider, db_path: str | Path) -> None:
        self._llm = llm
        self._db_path = db_path
        self._system_prompt = _load_system_prompt()

    async def suggest(
        self,
        code: str,
        language: str = "python",
    ) -> list[dict[str, Any]]:
        """Return a list of refactoring suggestions for the given code.

        Each suggestion contains: title, severity, description, before, after.
        """
        prompt = f"Language: {language}\n\n```{language}\n{code}\n```"

        start = time.monotonic()
        raw = await self._llm.generate(
            prompt,
            system=self._system_prompt,
            max_tokens=1024,
            temperature=0.3,
        )
        latency_ms = int((time.monotonic() - start) * 1000)

        suggestions = self._parse_suggestions(raw)
        self._record_usage(code, language, raw, latency_ms)
        return suggestions

    @staticmethod
    def _parse_suggestions(raw: str) -> list[dict[str, Any]]:
        """Best-effort JSON parsing of the LLM output."""
        text = raw.strip()
        if text.startswith("```"):
            lines = text.splitlines()
            text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
        try:
            parsed = json.loads(text)
            if isinstance(parsed, list):
                return parsed
            return [parsed]
        except json.JSONDecodeError:
            logger.warning("Failed to parse refactoring JSON, returning raw text")
            return [{"title": "Raw output", "severity": "info", "description": text, "before": "", "after": ""}]

    def _record_usage(
        self, code: str, language: str, result: str, latency_ms: int
    ) -> None:
        token_count = len(result.split())
        with get_db(self._db_path) as conn:
            conn.execute(
                """INSERT INTO conversations
                   (feature, input_code, input_language, output_text,
                    tokens_generated, latency_ms)
                   VALUES ('refactoring', ?, ?, ?, ?, ?)""",
                (code, language, result, token_count, latency_ms),
            )
