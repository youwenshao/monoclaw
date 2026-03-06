"""Weekly / on-demand analytics report generation from local DB."""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from openclaw_shared.database import get_db

logger = logging.getLogger(__name__)


def get_engagement_summary(
    db_path: str | Path,
    days: int = 7,
) -> dict[str, Any]:
    """Aggregate engagement metrics over the last *days* days.

    Returns totals and averages across all platform posts with analytics.
    """
    cutoff = (datetime.now() - timedelta(days=days)).isoformat()

    with get_db(db_path) as conn:
        row = conn.execute(
            """SELECT
                 COUNT(*) AS total_posts,
                 COALESCE(SUM(a.impressions), 0) AS total_impressions,
                 COALESCE(SUM(a.reach), 0) AS total_reach,
                 COALESCE(SUM(a.likes), 0) AS total_likes,
                 COALESCE(SUM(a.comments), 0) AS total_comments,
                 COALESCE(SUM(a.shares), 0) AS total_shares,
                 COALESCE(SUM(a.saves), 0) AS total_saves,
                 COALESCE(SUM(a.link_clicks), 0) AS total_link_clicks
               FROM analytics a
               JOIN platform_posts pp ON pp.id = a.platform_post_id
               JOIN posts p ON p.id = pp.post_id
               WHERE p.created_at >= ?""",
            (cutoff,),
        ).fetchone()

    summary = dict(row) if row else {}
    total = summary.get("total_posts", 0)
    if total > 0:
        summary["avg_likes"] = round(summary["total_likes"] / total, 1)
        summary["avg_comments"] = round(summary["total_comments"] / total, 1)
        summary["avg_shares"] = round(summary["total_shares"] / total, 1)
        total_engagement = (
            summary["total_likes"]
            + summary["total_comments"]
            + summary["total_shares"]
            + summary["total_saves"]
        )
        summary["engagement_rate"] = (
            round(total_engagement / summary["total_reach"] * 100, 2)
            if summary["total_reach"] > 0
            else 0.0
        )
    else:
        summary.update(avg_likes=0, avg_comments=0, avg_shares=0, engagement_rate=0.0)

    summary["period_days"] = days
    return summary


def _platform_breakdown(db_path: str | Path, cutoff: str) -> list[dict[str, Any]]:
    """Per-platform engagement breakdown."""
    with get_db(db_path) as conn:
        rows = conn.execute(
            """SELECT
                 pp.platform,
                 COUNT(*) AS posts,
                 COALESCE(SUM(a.impressions), 0) AS impressions,
                 COALESCE(SUM(a.reach), 0) AS reach,
                 COALESCE(SUM(a.likes), 0) AS likes,
                 COALESCE(SUM(a.comments), 0) AS comments,
                 COALESCE(SUM(a.shares), 0) AS shares
               FROM platform_posts pp
               LEFT JOIN analytics a ON a.platform_post_id = pp.id
               JOIN posts p ON p.id = pp.post_id
               WHERE p.created_at >= ?
               GROUP BY pp.platform""",
            (cutoff,),
        ).fetchall()
    return [dict(r) for r in rows]


def _top_posts(db_path: str | Path, cutoff: str, limit: int = 5) -> list[dict[str, Any]]:
    """Return top-performing posts by total engagement."""
    with get_db(db_path) as conn:
        rows = conn.execute(
            """SELECT
                 p.id, p.content_text, p.created_at,
                 pp.platform,
                 COALESCE(a.likes, 0) + COALESCE(a.comments, 0)
                   + COALESCE(a.shares, 0) + COALESCE(a.saves, 0) AS engagement,
                 a.impressions, a.reach, a.likes, a.comments, a.shares, a.saves
               FROM posts p
               JOIN platform_posts pp ON pp.post_id = p.id
               LEFT JOIN analytics a ON a.platform_post_id = pp.id
               WHERE p.created_at >= ?
               ORDER BY engagement DESC
               LIMIT ?""",
            (cutoff, limit),
        ).fetchall()
    return [dict(r) for r in rows]


def generate_weekly_report(
    db_path: str | Path,
) -> dict[str, Any]:
    """Generate a comprehensive weekly performance report.

    Returns:
        Dict with ``summary``, ``platform_breakdown``, ``top_posts``,
        and ``period`` metadata.
    """
    now = datetime.now()
    cutoff = (now - timedelta(days=7)).isoformat()

    summary = get_engagement_summary(db_path, days=7)
    breakdown = _platform_breakdown(db_path, cutoff)
    top = _top_posts(db_path, cutoff)

    with get_db(db_path) as conn:
        published = conn.execute(
            "SELECT COUNT(*) FROM posts WHERE status = 'published' AND created_at >= ?",
            (cutoff,),
        ).fetchone()[0]
        scheduled = conn.execute(
            "SELECT COUNT(*) FROM posts WHERE status = 'scheduled'"
        ).fetchone()[0]

    return {
        "period": {
            "start": (now - timedelta(days=7)).strftime("%Y-%m-%d"),
            "end": now.strftime("%Y-%m-%d"),
        },
        "summary": summary,
        "platform_breakdown": breakdown,
        "top_posts": top,
        "posts_published": published,
        "posts_scheduled": scheduled,
    }
