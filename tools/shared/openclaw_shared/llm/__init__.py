"""LLM abstraction layer with pluggable backends."""

from openclaw_shared.llm.base import LLMProvider
from openclaw_shared.llm.mock_adapter import MockLLMProvider

__all__ = ["LLMProvider", "MockLLMProvider", "create_llm_provider"]


def create_llm_provider(provider: str, **kwargs: object) -> LLMProvider:
    """Factory to instantiate the configured LLM provider."""
    if provider == "mock":
        return MockLLMProvider()
    if provider == "mlx":
        from openclaw_shared.llm.mlx_adapter import MLXLLMProvider
        return MLXLLMProvider(**kwargs)  # type: ignore[arg-type]
    raise ValueError(f"Unknown LLM provider: {provider}")
