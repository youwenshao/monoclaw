"""Facebook Pages API publisher for posts and stories."""

from __future__ import annotations

from typing import Any

import httpx

GRAPH_API_BASE = "https://graph.facebook.com/v19.0"


class FacebookPublisher:
    """Publish content to a Facebook Page via the Pages API.

    Requires the page ID and a page access token with ``pages_manage_posts``
    and ``pages_read_engagement`` permissions.
    """

    def __init__(self, page_id: str, access_token: str) -> None:
        self.page_id = page_id
        self.access_token = access_token
        self._base = f"{GRAPH_API_BASE}/{self.page_id}"

    async def _request(self, method: str, url: str, **kwargs: Any) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.request(method, url, **kwargs)
            resp.raise_for_status()
            return resp.json()

    async def publish_post(
        self,
        message: str,
        image_url: str | None = None,
    ) -> dict[str, Any]:
        """Publish a text or photo post to the page feed."""
        if image_url:
            result = await self._request(
                "POST",
                f"{self._base}/photos",
                params={
                    "url": image_url,
                    "caption": message,
                    "access_token": self.access_token,
                },
            )
            return {
                "platform": "facebook_page",
                "post_id": result.get("post_id") or result.get("id"),
                "status": "published",
            }

        result = await self._request(
            "POST",
            f"{self._base}/feed",
            params={
                "message": message,
                "access_token": self.access_token,
            },
        )
        return {"platform": "facebook_page", "post_id": result.get("id"), "status": "published"}

    async def publish_story(self, image_url: str) -> dict[str, Any]:
        """Publish a photo as a Facebook Page Story.

        Facebook Page Stories API requires a photo upload step.
        """
        upload = await self._request(
            "POST",
            f"{self._base}/photo_stories",
            params={
                "photo_url": image_url,
                "access_token": self.access_token,
            },
        )
        return {
            "platform": "facebook_story",
            "post_id": upload.get("post_id") or upload.get("id"),
            "status": "published",
        }
