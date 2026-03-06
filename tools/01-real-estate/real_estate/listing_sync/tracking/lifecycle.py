"""Listing status lifecycle management.

Handles status transitions for listings and propagates changes
to all associated platform_posts records.
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

from openclaw_shared.database import get_db

logger = logging.getLogger("listing_sync.tracking.lifecycle")

VALID_STATUSES = {"active", "pending", "sold", "let", "withdrawn", "expired"}

STATUS_TRANSITIONS: dict[str, set[str]] = {
    "active": {"pending", "sold", "let", "withdrawn", "expired"},
    "pending": {"active", "withdrawn"},
    "sold": {"active"},
    "let": {"active"},
    "withdrawn": {"active"},
    "expired": {"active"},
}

PLATFORM_STATUS_MAP: dict[str, str] = {
    "active": "posted",
    "pending": "paused",
    "sold": "removed",
    "let": "removed",
    "withdrawn": "removed",
    "expired": "expired",
}


def update_listing_status(
    db_path: str | Path,
    listing_id: int,
    new_status: str,
) -> dict:
    """Update a listing's status and cascade to all platform_posts.

    Returns a summary of changes made.
    """
    new_status = new_status.lower().strip()
    if new_status not in VALID_STATUSES:
        return {"error": f"Invalid status '{new_status}'. Valid: {', '.join(sorted(VALID_STATUSES))}"}

    with get_db(db_path) as conn:
        row = conn.execute("SELECT id, status FROM listings WHERE id = ?", (listing_id,)).fetchone()
        if not row:
            return {"error": f"Listing {listing_id} not found"}

        old_status = row["status"]
        allowed = STATUS_TRANSITIONS.get(old_status, set())
        if new_status not in allowed and old_status != new_status:
            return {
                "error": f"Cannot transition from '{old_status}' to '{new_status}'",
                "allowed_transitions": sorted(allowed),
            }

        if old_status == new_status:
            return {"listing_id": listing_id, "status": new_status, "changed": False}

        conn.execute(
            "UPDATE listings SET status = ?, updated_at = ? WHERE id = ?",
            (new_status, datetime.utcnow().isoformat(), listing_id),
        )

        platform_status = PLATFORM_STATUS_MAP.get(new_status, "pending")
        conn.execute(
            "UPDATE platform_posts SET status = ?, last_checked = ? WHERE listing_id = ?",
            (platform_status, datetime.utcnow().isoformat(), listing_id),
        )

        affected = conn.execute(
            "SELECT COUNT(*) FROM platform_posts WHERE listing_id = ?", (listing_id,)
        ).fetchone()[0]

    logger.info(
        "Listing %d: %s -> %s (propagated '%s' to %d platform posts)",
        listing_id, old_status, new_status, platform_status, affected,
    )

    return {
        "listing_id": listing_id,
        "old_status": old_status,
        "new_status": new_status,
        "platform_status": platform_status,
        "platform_posts_updated": affected,
        "changed": True,
    }


def get_platform_statuses(db_path: str | Path, listing_id: int) -> dict:
    """Get per-platform status breakdown for a listing."""
    with get_db(db_path) as conn:
        row = conn.execute("SELECT id, status FROM listings WHERE id = ?", (listing_id,)).fetchone()
        if not row:
            return {"error": f"Listing {listing_id} not found"}

        posts = conn.execute(
            """SELECT platform, platform_listing_id, status, posted_at, last_checked,
                      views, inquiries
               FROM platform_posts WHERE listing_id = ?""",
            (listing_id,),
        ).fetchall()

    return {
        "listing_id": listing_id,
        "listing_status": row["status"],
        "platforms": {
            p["platform"]: {
                "platform_listing_id": p["platform_listing_id"],
                "status": p["status"],
                "posted_at": p["posted_at"],
                "last_checked": p["last_checked"],
                "views": p["views"],
                "inquiries": p["inquiries"],
            }
            for p in posts
        },
    }
