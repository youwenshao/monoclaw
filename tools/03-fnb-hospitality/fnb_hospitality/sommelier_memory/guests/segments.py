"""VIP tier auto-classification and custom tagging."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from openclaw_shared.database import get_db
from openclaw_shared.mona_events import emit_event

logger = logging.getLogger("openclaw.fnb-hospitality.sommelier-memory.segments")

DEFAULT_THRESHOLDS = {
    "vip_min_visits": 5,
    "vip_min_spend": 10000,
    "vvip_min_visits": 15,
    "vvip_min_spend": 50000,
}


def classify_tier(
    total_visits: int,
    total_spend: float,
    thresholds: dict[str, Any] | None = None,
) -> str:
    t = {**DEFAULT_THRESHOLDS, **(thresholds or {})}
    if total_visits >= t["vvip_min_visits"] and total_spend >= t["vvip_min_spend"]:
        return "vvip"
    if total_visits >= t["vip_min_visits"] and total_spend >= t["vip_min_spend"]:
        return "vip"
    return "regular"


def refresh_all_tiers(
    db_path: str | Path,
    thresholds: dict[str, Any] | None = None,
    *,
    mona_db: str | Path | None = None,
) -> dict[str, int]:
    """Re-classify all guests and return counts per tier."""
    t = {**DEFAULT_THRESHOLDS, **(thresholds or {})}
    counts = {"regular": 0, "vip": 0, "vvip": 0}
    changed = 0
    now = datetime.now().isoformat()

    with get_db(db_path) as conn:
        guests = conn.execute(
            "SELECT id, total_visits, total_spend, vip_tier FROM sm_guests"
        ).fetchall()

        for g in guests:
            guest_id, visits, spend, current_tier = g[0], g[1] or 0, g[2] or 0.0, g[3]
            new_tier = classify_tier(visits, spend, t)
            counts[new_tier] += 1

            if new_tier != current_tier:
                conn.execute(
                    "UPDATE sm_guests SET vip_tier = ?, updated_at = ? WHERE id = ?",
                    (new_tier, now, guest_id),
                )
                changed += 1
                logger.info("Guest #%d tier changed: %s -> %s", guest_id, current_tier, new_tier)

    if mona_db:
        emit_event(
            mona_db,
            event_type="action_completed",
            tool_name="sommelier-memory",
            summary=f"VIP tiers refreshed: {changed} changed — VVIP:{counts['vvip']} VIP:{counts['vip']} Regular:{counts['regular']}",
            details=json.dumps({"thresholds": t, "counts": counts, "changed": changed}),
        )

    return counts


def _parse_tags(tags_str: str | None) -> list[str]:
    if not tags_str:
        return []
    return [t.strip() for t in tags_str.split(",") if t.strip()]


def _serialize_tags(tags: list[str]) -> str:
    return ",".join(sorted(set(tags)))


def add_tag(
    db_path: str | Path,
    guest_id: int,
    tag: str,
    *,
    mona_db: str | Path | None = None,
) -> list[str]:
    tag = tag.strip().lower()
    if not tag:
        raise ValueError("Tag cannot be empty")

    with get_db(db_path) as conn:
        row = conn.execute("SELECT tags FROM sm_guests WHERE id = ?", (guest_id,)).fetchone()
        if not row:
            raise ValueError(f"Guest {guest_id} not found")

        current = _parse_tags(row[0])
        if tag not in current:
            current.append(tag)

        new_tags = _serialize_tags(current)
        conn.execute(
            "UPDATE sm_guests SET tags = ?, updated_at = ? WHERE id = ?",
            (new_tags, datetime.now().isoformat(), guest_id),
        )

    if mona_db:
        emit_event(
            mona_db,
            event_type="info",
            tool_name="sommelier-memory",
            summary=f"Tag '{tag}' added to guest #{guest_id}",
        )

    return _parse_tags(new_tags)


def remove_tag(
    db_path: str | Path,
    guest_id: int,
    tag: str,
    *,
    mona_db: str | Path | None = None,
) -> list[str]:
    tag = tag.strip().lower()

    with get_db(db_path) as conn:
        row = conn.execute("SELECT tags FROM sm_guests WHERE id = ?", (guest_id,)).fetchone()
        if not row:
            raise ValueError(f"Guest {guest_id} not found")

        current = _parse_tags(row[0])
        current = [t for t in current if t != tag]

        new_tags = _serialize_tags(current)
        conn.execute(
            "UPDATE sm_guests SET tags = ?, updated_at = ? WHERE id = ?",
            (new_tags, datetime.now().isoformat(), guest_id),
        )

    if mona_db:
        emit_event(
            mona_db,
            event_type="info",
            tool_name="sommelier-memory",
            summary=f"Tag '{tag}' removed from guest #{guest_id}",
        )

    return _parse_tags(new_tags)
