"""Chat-based code Q&A engine with conversation history."""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import AsyncIterator

import yaml

from openclaw_shared.database import get_db
from openclaw_shared.llm.base import LLMProvider

logger = logging.getLogger("vibe-coder.code_qwen.chat")

PROMPTS_PATH = Path(__file__).resolve().parent.parent / "prompts" / "system_prompts.yaml"

MAX_HISTORY_TURNS = 10


def _load_system_prompt() -> str:
    with open(PROMPTS_PATH) as f:
        prompts = yaml.safe_load(f)
    return prompts["chat"]


class ChatEngine:
    """Conversational code Q&A that tracks session history."""

    def __init__(self, llm: LLMProvider, db_path: str | Path) -> None:
        self._llm = llm
        self._db_path = db_path
        self._system_prompt = _load_system_prompt()

    def _get_history(self, session_id: str) -> list[dict[str, str]]:
        """Load recent conversation turns for the session."""
        with get_db(self._db_path) as conn:
            rows = conn.execute(
                """SELECT input_code, output_text FROM conversations
                   WHERE session_id = ? AND feature = 'chat'
                   ORDER BY created_at DESC LIMIT ?""",
                (session_id, MAX_HISTORY_TURNS),
            ).fetchall()

        history: list[dict[str, str]] = []
        for row in reversed(rows):
            history.append({"role": "user", "content": row["input_code"]})
            history.append({"role": "assistant", "content": row["output_text"]})
        return history

    def _build_prompt(self, message: str, session_id: str, language: str) -> str:
        """Build a prompt incorporating conversation history."""
        history = self._get_history(session_id)
        parts = []
        for turn in history:
            prefix = "User" if turn["role"] == "user" else "Assistant"
            parts.append(f"{prefix}: {turn['content']}")
        parts.append(f"User: [Language context: {language}]\n{message}")
        return "\n\n".join(parts)

    def _save_turn(
        self,
        session_id: str,
        message: str,
        response: str,
        language: str,
        latency_ms: int,
    ) -> None:
        token_count = len(response.split())
        with get_db(self._db_path) as conn:
            conn.execute(
                """INSERT INTO conversations
                   (session_id, feature, input_code, input_language, output_text,
                    tokens_generated, latency_ms)
                   VALUES (?, 'chat', ?, ?, ?, ?, ?)""",
                (session_id, message, language, response, token_count, latency_ms),
            )

    async def chat(
        self,
        message: str,
        session_id: str = "default",
        language: str = "python",
    ) -> str:
        """Send a message and get a non-streaming response."""
        prompt = self._build_prompt(message, session_id, language)
        start = time.monotonic()
        response = await self._llm.generate(
            prompt,
            system=self._system_prompt,
            max_tokens=1024,
            temperature=0.7,
        )
        latency_ms = int((time.monotonic() - start) * 1000)
        self._save_turn(session_id, message, response, language, latency_ms)
        return response

    async def chat_stream(
        self,
        message: str,
        session_id: str = "default",
        language: str = "python",
    ) -> AsyncIterator[str]:
        """Stream a chat response token-by-token."""
        prompt = self._build_prompt(message, session_id, language)
        start = time.monotonic()
        tokens: list[str] = []

        async for token in self._llm.generate_stream(
            prompt,
            system=self._system_prompt,
            max_tokens=1024,
            temperature=0.7,
        ):
            tokens.append(token)
            yield token

        latency_ms = int((time.monotonic() - start) * 1000)
        full_response = "".join(tokens)
        self._save_turn(session_id, message, full_response, language, latency_ms)
