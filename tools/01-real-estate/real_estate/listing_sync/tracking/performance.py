"""Cross-platform performance tracking and analytics."""

from __future__ import annotations

import logging
from pathlib import Path

from openclaw_shared.database import get_db

logger = logging.getLogger("listing_sync.tracking.performance")


def get_performance_summary(db_path: str | Path) -> dict:
    """Aggregate listing performance across all platforms.

    Returns views, inquiries, and average days-on-market broken down
    by platform, plus overall totals.
    """
    with get_db(db_path) as conn:
        per_platform = conn.execute("""
            SELECT
                pp.platform,
                COUNT(DISTINCT pp.listing_id) AS listing_count,
                COALESCE(SUM(pp.views), 0) AS total_views,
                COALESCE(SUM(pp.inquiries), 0) AS total_inquiries,
                ROUND(AVG(
                    julianday(COALESCE(pp.last_checked, 'now'))
                    - julianday(pp.posted_at)
                ), 1) AS avg_days_on_market
            FROM platform_posts pp
            WHERE pp.posted_at IS NOT NULL
            GROUP BY pp.platform
        """).fetchall()

        totals = conn.execute("""
            SELECT
                COUNT(DISTINCT pp.listing_id) AS total_listings,
                COALESCE(SUM(pp.views), 0) AS total_views,
                COALESCE(SUM(pp.inquiries), 0) AS total_inquiries,
                ROUND(AVG(
                    julianday(COALESCE(pp.last_checked, 'now'))
                    - julianday(pp.posted_at)
                ), 1) AS avg_days_on_market
            FROM platform_posts pp
            WHERE pp.posted_at IS NOT NULL
        """).fetchone()

        top_performers = conn.execute("""
            SELECT
                l.reference_code,
                l.title_en,
                l.district,
                SUM(pp.views) AS total_views,
                SUM(pp.inquiries) AS total_inquiries,
                CASE WHEN SUM(pp.views) > 0
                     THEN ROUND(CAST(SUM(pp.inquiries) AS REAL) / SUM(pp.views) * 100, 1)
                     ELSE 0.0
                END AS conversion_rate
            FROM platform_posts pp
            JOIN listings l ON l.id = pp.listing_id
            WHERE pp.posted_at IS NOT NULL
            GROUP BY pp.listing_id
            ORDER BY total_inquiries DESC, total_views DESC
            LIMIT 10
        """).fetchall()

    platforms = {}
    for row in per_platform:
        p = row["platform"]
        views = row["total_views"]
        inquiries = row["total_inquiries"]
        platforms[p] = {
            "listing_count": row["listing_count"],
            "total_views": views,
            "total_inquiries": inquiries,
            "avg_days_on_market": row["avg_days_on_market"] or 0,
            "conversion_rate": round(inquiries / views * 100, 1) if views > 0 else 0.0,
        }

    return {
        "totals": {
            "active_listings": totals["total_listings"] if totals else 0,
            "total_views": totals["total_views"] if totals else 0,
            "total_inquiries": totals["total_inquiries"] if totals else 0,
            "avg_days_on_market": totals["avg_days_on_market"] if totals else 0,
        },
        "by_platform": platforms,
        "top_performers": [
            {
                "reference_code": r["reference_code"],
                "title": r["title_en"],
                "district": r["district"],
                "total_views": r["total_views"],
                "total_inquiries": r["total_inquiries"],
                "conversion_rate": r["conversion_rate"],
            }
            for r in top_performers
        ],
    }
