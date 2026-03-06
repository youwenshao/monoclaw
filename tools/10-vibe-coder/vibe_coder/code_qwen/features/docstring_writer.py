"""Auto-generate docstrings using LLM analysis."""

from __future__ import annotations

import logging
import time
from pathlib import Path

import yaml

from openclaw_shared.database import get_db
from openclaw_shared.llm.base import LLMProvider

logger = logging.getLogger("vibe-coder.code_qwen.docstring")

PROMPTS_PATH = Path(__file__).resolve().parent.parent / "prompts" / "system_prompts.yaml"

STYLE_HINTS = {
    "google": "Use Google-style docstrings (Args:, Returns:, Raises: sections).",
    "numpy": "Use NumPy-style docstrings (Parameters, Returns, Raises sections with dashes).",
    "pep257": "Use standard PEP 257 docstrings.",
    "jsdoc": "Use JSDoc format with @param, @returns, @throws tags.",
    "rustdoc": "Use rustdoc format with # Examples sections.",
    "godoc": "Use godoc-style comments.",
}


def _load_system_prompt() -> str:
    with open(PROMPTS_PATH) as f:
        prompts = yaml.safe_load(f)
    return prompts["docstring"]


class DocstringWriter:
    """Generates documentation strings matching language and style conventions."""

    def __init__(self, llm: LLMProvider, db_path: str | Path) -> None:
        self._llm = llm
        self._db_path = db_path
        self._system_prompt = _load_system_prompt()

    async def generate(
        self,
        code: str,
        language: str = "python",
        style: str = "google",
    ) -> str:
        """Generate a docstring for the provided code.

        Args:
            code: The function/class/method source code.
            language: Programming language.
            style: Docstring style (google, numpy, pep257, jsdoc, rustdoc, godoc).

        Returns:
            The generated docstring text.
        """
        style_hint = STYLE_HINTS.get(style, STYLE_HINTS["google"])
        prompt = (
            f"Language: {language}\n"
            f"Style: {style_hint}\n\n"
            f"```{language}\n{code}\n```"
        )

        start = time.monotonic()
        result = await self._llm.generate(
            prompt,
            system=self._system_prompt,
            max_tokens=512,
            temperature=0.2,
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
                   VALUES ('docstring', ?, ?, ?, ?, ?)""",
                (code, language, result, token_count, latency_ms),
            )
