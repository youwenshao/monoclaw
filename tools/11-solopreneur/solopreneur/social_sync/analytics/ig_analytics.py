"""Instagram Graph API analytics fetchers."""

from __future__ import annotations

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

GRAPH_API_BASE = "https://graph.facebook.com/v19.0"

POST_INSIGHT_METRICS = "impressions,reach,likes,comments,saved,shares"
ACCOUNT_INSIGHT_METRICS = "impressions,reach,profile_views,website_clicks,follower_count"


async def _get(url: str, params: dict[str, str]) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(url, params=params)
        resp.raise_for_status()
        return resp.json()


async def fetch_post_insights(
    access_token: str,
    media_id: str,
) -> dict[str, Any]:
    """Fetch engagement insights for a single IG media object.

    Returns a flat dict of metric_name → value.
    """
    data = await _get(
        f"{GRAPH_API_BASE}/{media_id}/insights",
        params={
            "metric": POST_INSIGHT_METRICS,
            "access_token": access_token,
        },
    )

    metrics: dict[str, Any] = {"media_id": media_id}
    for item in data.get("data", []):
        name = item.get("name", "")
        values = item.get("values", [{}])
        metrics[name] = values[0].get("value", 0) if values else 0

    return metrics


async def fetch_account_insights(
    access_token: str,
    business_id: str,
    period: str = "day",
) -> dict[str, Any]:
    """Fetch account-level insights for the IG business account.

    Args:
        period: One of ``day``, ``week``, ``days_28``, ``lifetime``.

    Returns:
        Dict with metric name → list of time-series values.
    """
    data = await _get(
        f"{GRAPH_API_BASE}/{business_id}/insights",
        params={
            "metric": ACCOUNT_INSIGHT_METRICS,
            "period": period,
            "access_token": access_token,
        },
    )

    metrics: dict[str, Any] = {"business_id": business_id, "period": period}
    for item in data.get("data", []):
        name = item.get("name", "")
        metrics[name] = item.get("values", [])

    return metrics
