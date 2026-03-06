"""APScheduler-based post scheduling for deferred publishing."""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from openclaw_shared.database import get_db

logger = logging.getLogger(__name__)


def schedule_post(
    scheduler: Any,
    post_id: int,
    publish_time: datetime,
    publish_fn: Callable[..., Any],
    **kwargs: Any,
) -> str:
    """Schedule *publish_fn* to run at *publish_time* for *post_id*.

    Args:
        scheduler: An APScheduler ``AsyncIOScheduler`` (or compatible) instance.
        post_id: ID of the post in the ``posts`` table.
        publish_time: When to fire the job (timezone-aware preferred).
        publish_fn: Async callable invoked with ``post_id`` plus **kwargs.

    Returns:
        The APScheduler job ID string.
    """
    job_id = f"socialsync_publish_{post_id}"

    scheduler.add_job(
        publish_fn,
        trigger="date",
        run_date=publish_time,
        id=job_id,
        replace_existing=True,
        kwargs={"post_id": post_id, **kwargs},
    )

    logger.info("Scheduled post %d for %s (job=%s)", post_id, publish_time, job_id)
    return job_id


def cancel_scheduled_post(scheduler: Any, job_id: str) -> bool:
    """Remove a scheduled job. Returns ``True`` if successfully removed."""
    try:
        scheduler.remove_job(job_id)
        logger.info("Cancelled scheduled job %s", job_id)
        return True
    except Exception as exc:
        logger.warning("Could not cancel job %s: %s", job_id, exc)
        return False


def get_scheduled_posts(db_path: str | Path) -> list[dict[str, Any]]:
    """Return all posts with status 'scheduled', ordered by scheduled_time."""
    with get_db(db_path) as conn:
        rows = conn.execute(
            """SELECT p.*, GROUP_CONCAT(pp.platform) AS platforms
               FROM posts p
               LEFT JOIN platform_posts pp ON pp.post_id = p.id
               WHERE p.status = 'scheduled'
               GROUP BY p.id
               ORDER BY p.scheduled_time ASC"""
        ).fetchall()
    return [dict(r) for r in rows]
