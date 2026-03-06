"""Orchestrate simultaneous cross-platform publishing with error isolation."""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from openclaw_shared.database import get_db

logger = logging.getLogger(__name__)


async def publish_to_platform(
    post_data: dict[str, Any],
    publisher: Any,
    platform: str,
) -> dict[str, Any]:
    """Publish *post_data* to a single *platform* via *publisher*.

    Returns a result dict with ``platform``, ``status``, and optionally
    ``platform_post_id`` or ``error``.
    """
    try:
        image_paths = json.loads(post_data.get("image_paths") or "[]")
        first_image = image_paths[0] if image_paths else None
        video_path = post_data.get("video_path")
        caption = post_data.get("content_text", "")
        hashtags = json.loads(post_data.get("hashtags") or "[]")

        if platform == "instagram_feed" and first_image:
            return await publisher.publish_feed(first_image, caption, hashtags)
        elif platform == "instagram_story" and first_image:
            return await publisher.publish_story(first_image)
        elif platform == "instagram_reel" and video_path:
            return await publisher.publish_reel(video_path, caption)
        elif platform == "facebook_page":
            return await publisher.publish_post(caption, first_image)
        elif platform == "facebook_story" and first_image:
            return await publisher.publish_story(first_image)
        elif platform == "whatsapp_status":
            return publisher.publish_status(caption, first_image)
        else:
            return {
                "platform": platform,
                "status": "failed",
                "error": f"Unsupported platform/media combination: {platform}",
            }
    except Exception as exc:
        logger.error("Publishing to %s failed: %s", platform, exc)
        return {"platform": platform, "status": "failed", "error": str(exc)}


async def publish_to_all(
    post_data: dict[str, Any],
    publishers: dict[str, Any],
    db_path: str | Path,
) -> dict[str, Any]:
    """Publish a post to all targeted platforms concurrently.

    Args:
        post_data: Row from the ``posts`` table (as dict).
        publishers: Mapping of platform name to publisher instance.
        db_path: Path to the socialsync database.

    Returns:
        Dict with ``post_id``, ``results`` (per platform), and ``summary``.
    """
    post_id = post_data["id"]

    with get_db(db_path) as conn:
        conn.execute(
            "UPDATE posts SET status = 'publishing' WHERE id = ?",
            (post_id,),
        )

    tasks = []
    platform_names = []
    for platform, publisher in publishers.items():
        tasks.append(publish_to_platform(post_data, publisher, platform))
        platform_names.append(platform)

    raw_results = await asyncio.gather(*tasks, return_exceptions=True)

    results: list[dict[str, Any]] = []
    succeeded = 0
    failed = 0

    for platform, result in zip(platform_names, raw_results):
        if isinstance(result, Exception):
            result = {"platform": platform, "status": "failed", "error": str(result)}

        status = "published" if result.get("status") == "published" else "failed"
        platform_post_id = (
            result.get("media_id") or result.get("post_id") or None
        )
        error_msg = result.get("error")

        with get_db(db_path) as conn:
            conn.execute(
                """INSERT INTO platform_posts
                   (post_id, platform, platform_post_id, publish_status, published_at, error_message)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    post_id,
                    platform,
                    platform_post_id,
                    status,
                    datetime.now().isoformat() if status == "published" else None,
                    error_msg,
                ),
            )

        if status == "published":
            succeeded += 1
        else:
            failed += 1

        results.append(result)

    final_status = "published" if succeeded > 0 else "failed"
    with get_db(db_path) as conn:
        conn.execute(
            "UPDATE posts SET status = ? WHERE id = ?",
            (final_status, post_id),
        )

    return {
        "post_id": post_id,
        "results": results,
        "summary": {"succeeded": succeeded, "failed": failed, "total": len(results)},
    }
