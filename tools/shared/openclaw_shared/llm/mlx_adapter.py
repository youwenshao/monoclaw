"""Real MLX-based LLM provider for Apple Silicon Macs."""

from __future__ import annotations

import asyncio
import logging
from typing import AsyncIterator

from openclaw_shared.llm.base import LLMProvider

logger = logging.getLogger("openclaw.llm.mlx")


class MLXLLMProvider(LLMProvider):
    """Wraps mlx-lm for local inference on Apple Silicon.

    Requires the `mlx` optional extra to be installed.
    Model loading is lazy — triggered on first generate() or embed() call.
    """

    def __init__(
        self,
        model_path: str = "mlx-community/Qwen2.5-7B-Instruct-4bit",
        embedding_model_path: str = "BAAI/bge-base-zh-v1.5",
    ) -> None:
        self._model_path = model_path
        self._embedding_model_path = embedding_model_path
        self._model = None
        self._tokenizer = None
        self._embedding_model = None
        self._embedding_tokenizer = None

    def _load_model(self) -> None:
        if self._model is not None:
            return
        try:
            from mlx_lm import load  # type: ignore[import-untyped]
            logger.info("Loading LLM model from %s", self._model_path)
            self._model, self._tokenizer = load(self._model_path)
            logger.info("LLM model loaded successfully")
        except ImportError:
            raise RuntimeError(
                "mlx-lm is not installed. Install with: pip install 'openclaw-shared[mlx]'"
            )

    def _load_embedding_model(self) -> None:
        if self._embedding_model is not None:
            return
        try:
            from sentence_transformers import SentenceTransformer  # type: ignore[import-untyped]
            logger.info("Loading embedding model from %s", self._embedding_model_path)
            self._embedding_model = SentenceTransformer(self._embedding_model_path)
            logger.info("Embedding model loaded")
        except ImportError:
            raise RuntimeError("sentence-transformers is not installed.")

    async def generate(
        self,
        prompt: str,
        *,
        system: str = "",
        max_tokens: int = 512,
        temperature: float = 0.7,
    ) -> str:
        self._load_model()
        from mlx_lm import generate as mlx_generate  # type: ignore[import-untyped]

        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        formatted = self._tokenizer.apply_chat_template(  # type: ignore[union-attr]
            messages, tokenize=False, add_generation_prompt=True
        )

        result = await asyncio.to_thread(
            mlx_generate,
            self._model,
            self._tokenizer,
            prompt=formatted,
            max_tokens=max_tokens,
            temp=temperature,
        )
        return result

    async def generate_stream(
        self,
        prompt: str,
        *,
        system: str = "",
        max_tokens: int = 512,
        temperature: float = 0.7,
    ) -> AsyncIterator[str]:
        self._load_model()
        from mlx_lm import stream_generate  # type: ignore[import-untyped]

        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        formatted = self._tokenizer.apply_chat_template(  # type: ignore[union-attr]
            messages, tokenize=False, add_generation_prompt=True
        )

        generator = stream_generate(
            self._model,
            self._tokenizer,
            prompt=formatted,
            max_tokens=max_tokens,
            temp=temperature,
        )

        for token_text in generator:
            yield token_text
            await asyncio.sleep(0)

    async def embed(self, texts: list[str]) -> list[list[float]]:
        self._load_embedding_model()
        vectors = await asyncio.to_thread(self._embedding_model.encode, texts)  # type: ignore[union-attr]
        return vectors.tolist()

    async def health(self) -> dict[str, str]:
        status = "loaded" if self._model is not None else "unloaded"
        return {"provider": "mlx", "status": status, "model": self._model_path}
