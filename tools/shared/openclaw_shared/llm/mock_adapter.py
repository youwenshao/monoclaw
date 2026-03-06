"""Mock LLM provider for development and testing."""

from __future__ import annotations

import hashlib
from typing import AsyncIterator

from openclaw_shared.llm.base import LLMProvider


class MockLLMProvider(LLMProvider):
    """Deterministic mock that returns template responses keyed on prompt content."""

    RESPONSE_TEMPLATES = {
        "describe": "This is a well-appointed property located in a prime district of Hong Kong. "
        "The unit features excellent natural lighting, modern finishes, and convenient access to MTR. "
        "Saleable area as specified, with mountain/sea views from upper floors.",
        "search": '{"results": [{"building": "Mock Tower", "district": "Central", '
        '"price_hkd": 12800000, "saleable_sqft": 450}]}',
        "compare": "| Feature | Property A | Property B |\n|---------|-----------|----------|\n"
        "| Price/sqft | $28,444 | $26,200 |\n| Age | 15 years | 22 years |",
        "rewrite": "精選單位，交通便利，鄰近港鐵站。實用面積寬敞，景觀開揚。",
        "intent": '{"intent": "viewing_request", "property_ref": "MOCK-001", '
        '"preferred_datetime": "2026-03-10T15:00:00", "party_size": 1}',
        "answer": "Based on available records, this building was completed in 2005, "
        "features a clubhouse with swimming pool, and allows pets under 20kg. "
        "The management fee is approximately $3.2 per square foot.",
    }

    async def generate(
        self,
        prompt: str,
        *,
        system: str = "",
        max_tokens: int = 512,
        temperature: float = 0.7,
    ) -> str:
        prompt_lower = prompt.lower()
        for keyword, response in self.RESPONSE_TEMPLATES.items():
            if keyword in prompt_lower:
                return response
        return f"[Mock LLM response for prompt of {len(prompt)} chars]"

    async def generate_stream(
        self,
        prompt: str,
        *,
        system: str = "",
        max_tokens: int = 512,
        temperature: float = 0.7,
    ) -> AsyncIterator[str]:
        full = await self.generate(prompt, system=system, max_tokens=max_tokens)
        for word in full.split():
            yield word + " "

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Generate deterministic 384-dim vectors from text hashes."""
        vectors = []
        for text in texts:
            digest = hashlib.sha384(text.encode()).digest()
            vector = [b / 255.0 for b in digest]
            vectors.append(vector)
        return vectors

    async def health(self) -> dict[str, str]:
        return {"provider": "mock", "status": "loaded"}
