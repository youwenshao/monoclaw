"""FIM (fill-in-middle) completion engine with SQLite caching."""

from __future__ import annotations

import hashlib
import logging
import time
from pathlib import Path
from typing import AsyncIterator

import yaml

from openclaw_shared.database import get_db
from openclaw_shared.llm.base import LLMProvider

logger = logging.getLogger("vibe-coder.code_qwen.completion")

PROMPTS_PATH = Path(__file__).resolve().parent.parent / "prompts" / "system_prompts.yaml"

FIM_PREFIX = "<|fim_prefix|>"
FIM_SUFFIX = "<|fim_suffix|>"
FIM_MIDDLE = "<|fim_middle|>"


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:32]


def _load_system_prompt() -> str:
    with open(PROMPTS_PATH) as f:
        prompts = yaml.safe_load(f)
    return prompts["completion"]


class CompletionEngine:
    """Fill-in-the-middle code completion backed by Qwen-2.5-Coder."""

    def __init__(self, llm: LLMProvider, db_path: str | Path) -> None:
        self._llm = llm
        self._db_path = db_path
        self._system_prompt = _load_system_prompt()

    def _check_cache(self, prefix_hash: str, suffix_hash: str, language: str) -> str | None:
        with get_db(self._db_path) as conn:
            row = conn.execute(
                """SELECT id, completion FROM completions_cache
                   WHERE prefix_hash = ? AND suffix_hash = ? AND language = ?
                   ORDER BY hit_count DESC LIMIT 1""",
                (prefix_hash, suffix_hash, language),
            ).fetchone()
            if row:
                conn.execute(
                    "UPDATE completions_cache SET hit_count = hit_count + 1 WHERE id = ?",
                    (row["id"],),
                )
                return row["completion"]
        return None

    def _store_cache(
        self, prefix_hash: str, suffix_hash: str, language: str, completion: str, confidence: float
    ) -> None:
        with get_db(self._db_path) as conn:
            conn.execute(
                """INSERT INTO completions_cache
                   (prefix_hash, suffix_hash, language, completion, confidence)
                   VALUES (?, ?, ?, ?, ?)""",
                (prefix_hash, suffix_hash, language, completion, confidence),
            )

    def _build_fim_prompt(self, prefix: str, suffix: str) -> str:
        return f"{FIM_PREFIX}{prefix}{FIM_SUFFIX}{suffix}{FIM_MIDDLE}"

    async def complete(
        self,
        prefix: str,
        suffix: str,
        language: str = "python",
        max_tokens: int = 256,
    ) -> str:
        """Generate a FIM completion, returning cached results when available."""
        prefix_hash = _hash(prefix)
        suffix_hash = _hash(suffix)

        cached = self._check_cache(prefix_hash, suffix_hash, language)
        if cached is not None:
            logger.debug("Cache hit for completion")
            return cached

        prompt = self._build_fim_prompt(prefix, suffix)
        start = time.monotonic()
        result = await self._llm.generate(
            prompt,
            system=self._system_prompt,
            max_tokens=max_tokens,
            temperature=0.2,
        )
        latency_ms = int((time.monotonic() - start) * 1000)

        self._store_cache(prefix_hash, suffix_hash, language, result, confidence=0.8)
        self._record_usage(language, result, latency_ms)
        return result

    async def complete_stream(
        self,
        prefix: str,
        suffix: str,
        language: str = "python",
        max_tokens: int = 256,
    ) -> AsyncIterator[str]:
        """Stream FIM completion tokens via the LLM provider."""
        prompt = self._build_fim_prompt(prefix, suffix)
        start = time.monotonic()
        tokens: list[str] = []

        async for token in self._llm.generate_stream(
            prompt,
            system=self._system_prompt,
            max_tokens=max_tokens,
            temperature=0.2,
        ):
            tokens.append(token)
            yield token

        latency_ms = int((time.monotonic() - start) * 1000)
        full_result = "".join(tokens)
        prefix_hash = _hash(prefix)
        suffix_hash = _hash(suffix)
        self._store_cache(prefix_hash, suffix_hash, language, full_result, confidence=0.8)
        self._record_usage(language, full_result, latency_ms)

    def _record_usage(self, language: str, result: str, latency_ms: int) -> None:
        token_count = len(result.split())
        with get_db(self._db_path) as conn:
            conn.execute(
                """INSERT INTO conversations
                   (feature, input_language, output_text, tokens_generated, latency_ms)
                   VALUES ('completion', ?, ?, ?, ?)""",
                (language, result, token_count, latency_ms),
            )
