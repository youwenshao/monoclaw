"""Abstract base class for listing platform adapters."""

from __future__ import annotations

from abc import ABC, abstractmethod


class PlatformAdapter(ABC):
    """Interface that all listing-platform integrations must implement."""

    PLATFORM_NAME: str = ""
    MAX_PHOTOS: int = 0
    IMAGE_SPEC: tuple[int, int] = (0, 0)

    @abstractmethod
    async def post_listing(self, listing: dict, images: list[str]) -> str:
        """Publish a new listing. Returns the platform-specific listing ID."""
        ...

    @abstractmethod
    async def update_listing(self, platform_id: str, listing: dict) -> bool:
        """Update an existing listing on the platform."""
        ...

    @abstractmethod
    async def remove_listing(self, platform_id: str) -> bool:
        """Remove / unpublish a listing from the platform."""
        ...

    @abstractmethod
    async def get_stats(self, platform_id: str) -> dict:
        """Fetch view/inquiry stats for a listing from the platform."""
        ...
