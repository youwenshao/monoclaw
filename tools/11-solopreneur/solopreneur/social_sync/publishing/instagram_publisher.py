"""Instagram Graph API publisher for feed posts, stories, and reels."""

from __future__ import annotations

from typing import Any

import httpx

GRAPH_API_BASE = "https://graph.facebook.com/v19.0"


class InstagramPublisher:
    """Publish content to Instagram Business via the Graph API.

    Requires a long-lived page access token and the IG business account ID.
    """

    def __init__(self, access_token: str, business_id: str) -> None:
        self.access_token = access_token
        self.business_id = business_id
        self._base = f"{GRAPH_API_BASE}/{self.business_id}"

    async def _request(self, method: str, url: str, **kwargs: Any) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.request(method, url, **kwargs)
            resp.raise_for_status()
            return resp.json()

    async def publish_feed(
        self,
        image_url: str,
        caption: str,
        hashtags: list[str] | None = None,
    ) -> dict[str, Any]:
        """Publish a single-image feed post.

        Two-step process: create media container, then publish it.
        """
        full_caption = caption
        if hashtags:
            full_caption += "\n\n" + " ".join(f"#{h.lstrip('#')}" for h in hashtags)

        container = await self._request(
            "POST",
            f"{self._base}/media",
            params={
                "image_url": image_url,
                "caption": full_caption,
                "access_token": self.access_token,
            },
        )
        container_id = container["id"]

        result = await self._request(
            "POST",
            f"{self._base}/media_publish",
            params={
                "creation_id": container_id,
                "access_token": self.access_token,
            },
        )
        return {"platform": "instagram_feed", "media_id": result.get("id"), "status": "published"}

    async def publish_story(self, image_url: str) -> dict[str, Any]:
        """Publish an image as an Instagram Story."""
        container = await self._request(
            "POST",
            f"{self._base}/media",
            params={
                "image_url": image_url,
                "media_type": "STORIES",
                "access_token": self.access_token,
            },
        )
        container_id = container["id"]

        result = await self._request(
            "POST",
            f"{self._base}/media_publish",
            params={
                "creation_id": container_id,
                "access_token": self.access_token,
            },
        )
        return {"platform": "instagram_story", "media_id": result.get("id"), "status": "published"}

    async def publish_reel(self, video_url: str, caption: str) -> dict[str, Any]:
        """Publish a video as an Instagram Reel."""
        container = await self._request(
            "POST",
            f"{self._base}/media",
            params={
                "media_type": "REELS",
                "video_url": video_url,
                "caption": caption,
                "access_token": self.access_token,
            },
        )
        container_id = container["id"]

        # Reels take time to process — poll status before publishing
        import asyncio

        for _ in range(30):
            status = await self._request(
                "GET",
                f"{GRAPH_API_BASE}/{container_id}",
                params={
                    "fields": "status_code",
                    "access_token": self.access_token,
                },
            )
            if status.get("status_code") == "FINISHED":
                break
            await asyncio.sleep(2)

        result = await self._request(
            "POST",
            f"{self._base}/media_publish",
            params={
                "creation_id": container_id,
                "access_token": self.access_token,
            },
        )
        return {"platform": "instagram_reel", "media_id": result.get("id"), "status": "published"}
