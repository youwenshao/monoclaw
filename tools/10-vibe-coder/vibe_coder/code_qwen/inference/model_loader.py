"""Wraps openclaw_shared.llm for Qwen-2.5-Coder-7B with warm/cold management."""

from __future__ import annotations

import asyncio
import logging
import time

from openclaw_shared.llm import LLMProvider, create_llm_provider

logger = logging.getLogger("vibe-coder.code_qwen.model_loader")

DEFAULT_MODEL_PATH = "mlx-community/Qwen2.5-Coder-7B-Instruct-4bit"
COLD_TIMEOUT_SECONDS = 300


class CodeModelLoader:
    """Manages LLM provider lifecycle with warm/cold mode support.

    In *warm* mode the model stays loaded indefinitely.
    In *cold* mode the model is unloaded after a configurable inactivity period.
    """

    def __init__(
        self,
        provider_name: str = "mlx",
        model_path: str = DEFAULT_MODEL_PATH,
        mode: str = "warm",
        cold_timeout: int = COLD_TIMEOUT_SECONDS,
    ) -> None:
        self._provider_name = provider_name
        self._model_path = model_path
        self._mode = mode
        self._cold_timeout = cold_timeout
        self._provider: LLMProvider | None = None
        self._last_used: float = 0.0
        self._lock = asyncio.Lock()
        self._cold_task: asyncio.Task[None] | None = None

    async def get_provider(self) -> LLMProvider:
        """Return the LLM provider, loading it on first access."""
        async with self._lock:
            if self._provider is None:
                logger.info("Loading CodeQwen model (%s): %s", self._provider_name, self._model_path)
                self._provider = create_llm_provider(
                    self._provider_name, model_path=self._model_path
                )
                logger.info("CodeQwen model loaded")
            self._last_used = time.monotonic()
            if self._mode == "cold" and self._cold_task is None:
                self._cold_task = asyncio.create_task(self._cold_watcher())
            return self._provider

    def is_warm(self) -> bool:
        """Return True if the model is currently loaded in memory."""
        return self._provider is not None

    async def unload(self) -> None:
        """Explicitly unload the model to free memory."""
        async with self._lock:
            if self._cold_task is not None:
                self._cold_task.cancel()
                self._cold_task = None
            self._provider = None
            logger.info("CodeQwen model unloaded")

    async def _cold_watcher(self) -> None:
        """Background task that unloads the model after inactivity."""
        try:
            while True:
                await asyncio.sleep(self._cold_timeout)
                async with self._lock:
                    elapsed = time.monotonic() - self._last_used
                    if elapsed >= self._cold_timeout:
                        self._provider = None
                        self._cold_task = None
                        logger.info("Cold-mode: model unloaded after %ds inactivity", int(elapsed))
                        return
        except asyncio.CancelledError:
            return
