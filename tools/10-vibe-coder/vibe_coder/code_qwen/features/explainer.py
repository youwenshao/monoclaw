"""Code explanation feature using LLM-powered analysis."""

from __future__ import annotations

import logging
import time
from pathlib import Path

import yaml

from openclaw_shared.database import get_db
from openclaw_shared.llm.base import LLMProvider

logger = logging.getLogger("vibe-coder.code_qwen.explainer")

PROMPTS_PATH = Path(__file__).resolve().parent.parent / "prompts" / "system_prompts.yaml"

OUTPUT_LANGUAGE_MAP = {
    "en": "English",
    "zh": "Traditional Chinese (繁體中文)",
}


def _load_system_prompt(output_language: str) -> str:
    with open(PROMPTS_PATH) as f:
        prompts = yaml.safe_load(f)
    lang_name = OUTPUT_LANGUAGE_MAP.get(output_language, "English")
    return prompts["explanation"].replace("{output_language}", lang_name)


class CodeExplainer:
    """Generates structured explanations for code snippets."""

    def __init__(self, llm: LLMProvider, db_path: str | Path) -> None:
        self._llm = llm
        self._db_path = db_path

    async def explain(
        self,
        code: str,
        language: str = "python",
        output_language: str = "en",
    ) -> str:
        """Analyse code and return a structured explanation.

        Args:
            code: Source code to explain.
            language: Programming language of the code.
            output_language: ISO 639-1 code for the output language (en/zh).

        Returns:
            Markdown-formatted explanation.
        """
        system_prompt = _load_system_prompt(output_language)
        prompt = f"Language: {language}\n\n```{language}\n{code}\n```"

        start = time.monotonic()
        result = await self._llm.generate(
            prompt,
            system=system_prompt,
            max_tokens=1024,
            temperature=0.3,
        )
        latency_ms = int((time.monotonic() - start) * 1000)

        self._record_usage(code, language, result, latency_ms)
        return result

    def _record_usage(
        self, code: str, language: str, result: str, latency_ms: int
    ) -> None:
        token_count = len(result.split())
        with get_db(self._db_path) as conn:
            conn.execute(
                """INSERT INTO conversations
                   (feature, input_code, input_language, output_text,
                    tokens_generated, latency_ms)
                   VALUES ('explanation', ?, ?, ?, ?, ?)""",
                (code, language, result, token_count, latency_ms),
            )
