"""Abstract base class for LLM providers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import AsyncIterator


class LLMProvider(ABC):
    """Interface that all LLM backends must implement."""

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        *,
        system: str = "",
        max_tokens: int = 512,
        temperature: float = 0.7,
    ) -> str:
        """Generate a completion for the given prompt."""
        ...

    @abstractmethod
    async def generate_stream(
        self,
        prompt: str,
        *,
        system: str = "",
        max_tokens: int = 512,
        temperature: float = 0.7,
    ) -> AsyncIterator[str]:
        """Stream tokens as they are generated."""
        ...
        yield ""  # pragma: no cover

    @abstractmethod
    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Return embedding vectors for the given texts."""
        ...

    async def health(self) -> dict[str, str]:
        """Report provider health status."""
        return {"provider": self.__class__.__name__, "status": "unknown"}
