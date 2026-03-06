"""Facebook Pages API analytics fetchers."""

from __future__ import annotations

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

GRAPH_API_BASE = "https://graph.facebook.com/v19.0"

PAGE_INSIGHT_METRICS = (
    "page_impressions,page_engaged_users,page_fans,"
    "page_views_total,page_actions_post_reactions_total"
)
POST_FIELDS = "id,message,created_time,likes.summary(true),comments.summary(true),shares"


async def _get(url: str, params: dict[str, str]) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(url, params=params)
        resp.raise_for_status()
        return resp.json()


async def fetch_page_insights(
    access_token: str,
    page_id: str,
    period: str = "day",
) -> dict[str, Any]:
    """Fetch page-level insights for a Facebook Page.

    Args:
        period: ``day``, ``week``, or ``days_28``.

    Returns:
        Dict of metric name → list of time-series values.
    """
    data = await _get(
        f"{GRAPH_API_BASE}/{page_id}/insights",
        params={
            "metric": PAGE_INSIGHT_METRICS,
            "period": period,
            "access_token": access_token,
        },
    )

    metrics: dict[str, Any] = {"page_id": page_id, "period": period}
    for item in data.get("data", []):
        name = item.get("name", "")
        metrics[name] = item.get("values", [])

    return metrics


async def fetch_post_insights(
    access_token: str,
    post_id: str,
) -> dict[str, Any]:
    """Fetch engagement data for a single Facebook Page post."""
    data = await _get(
        f"{GRAPH_API_BASE}/{post_id}",
        params={
            "fields": POST_FIELDS,
            "access_token": access_token,
        },
    )

    likes = data.get("likes", {}).get("summary", {}).get("total_count", 0)
    comments = data.get("comments", {}).get("summary", {}).get("total_count", 0)
    shares = data.get("shares", {}).get("count", 0)

    return {
        "post_id": post_id,
        "message": data.get("message", ""),
        "created_time": data.get("created_time", ""),
        "likes": likes,
        "comments": comments,
        "shares": shares,
    }
