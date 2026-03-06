"""Base GovHK open-data API client with configurable TTL cache."""

from __future__ import annotations

import time
from typing import Any

import httpx


class GovHKClient:
    """Base async client for Hong Kong Government open-data APIs.

    Includes a simple in-memory TTL cache to avoid hammering public endpoints
    during rapid successive requests (e.g. dashboard polling).
    """

    WEATHER_BASE = "https://data.weather.gov.hk/weatherAPI/opendata/"
    DATA_BASE = "https://data.gov.hk/api/3/"

    def __init__(self, cache_ttl: int = 300) -> None:
        self._cache_ttl = cache_ttl
        self._cache: dict[str, tuple[float, Any]] = {}

    def _cache_key(self, url: str, params: dict | None) -> str:
        sorted_params = sorted((params or {}).items())
        return f"{url}?{'&'.join(f'{k}={v}' for k, v in sorted_params)}"

    def _get_cached(self, key: str) -> Any | None:
        if key in self._cache:
            ts, data = self._cache[key]
            if time.time() - ts < self._cache_ttl:
                return data
            del self._cache[key]
        return None

    def _set_cached(self, key: str, data: Any) -> None:
        self._cache[key] = (time.time(), data)

    async def _get(
        self,
        base_url: str,
        path: str,
        params: dict | None = None,
        timeout: float = 15,
    ) -> Any:
        url = f"{base_url}{path}"
        cache_key = self._cache_key(url, params)

        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        async with httpx.AsyncClient() as client:
            resp = await client.get(url, params=params, timeout=timeout)
            resp.raise_for_status()
            data = resp.json()

        self._set_cached(cache_key, data)
        return data

    async def get_weather(self, path: str, params: dict | None = None) -> Any:
        """Fetch from the HK Observatory weather API."""
        return await self._get(self.WEATHER_BASE, path, params)

    async def get_data(self, path: str, params: dict | None = None) -> Any:
        """Fetch from the data.gov.hk CKAN-style API."""
        return await self._get(self.DATA_BASE, path, params)

    def clear_cache(self) -> None:
        self._cache.clear()
