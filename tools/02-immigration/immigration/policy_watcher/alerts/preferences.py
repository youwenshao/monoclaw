"""Per-user alert subscription preferences and matching."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from openclaw_shared.database import get_db

logger = logging.getLogger("openclaw.immigration.policy_watcher.alerts.preferences")

URGENCY_LEVELS: dict[str, int] = {
    "routine": 0,
    "important": 1,
    "urgent": 2,
}


def _urgency_rank(level: str) -> int:
    return URGENCY_LEVELS.get(level.lower().strip(), 0)


def _schemes_overlap(subscription_filter: str | None, change_schemes: str | None) -> bool:
    """Check whether a subscription's scheme filter matches the change's affected schemes."""
    if not subscription_filter:
        return True
    if not change_schemes:
        return True

    sub_schemes = {s.strip().upper() for s in subscription_filter.split(",") if s.strip()}
    change_set = {s.strip().upper() for s in change_schemes.split(",") if s.strip()}

    if not sub_schemes:
        return True
    return bool(sub_schemes & change_set)


def get_matching_subscriptions(
    db_path: str | Path,
    change: dict[str, Any],
) -> list[dict[str, Any]]:
    """Return subscriptions that match the given policy change.

    Filters by:
    1. Active status (active = 1)
    2. Scheme overlap (subscription filter vs change's affected_schemes)
    3. Urgency threshold (only send if change urgency >= subscription threshold)
    """
    change_urgency = change.get("urgency", "routine")
    change_rank = _urgency_rank(change_urgency)
    change_schemes = change.get("affected_schemes", "")

    with get_db(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM alert_subscriptions WHERE active = 1"
        ).fetchall()

    matched: list[dict[str, Any]] = []
    for row in rows:
        sub = dict(row)

        threshold = sub.get("urgency_threshold", "important")
        if change_rank < _urgency_rank(threshold):
            continue

        if not _schemes_overlap(sub.get("schemes_filter"), change_schemes):
            continue

        matched.append(sub)

    logger.debug(
        "Matched %d/%d active subscriptions for change urgency=%s schemes=%s",
        len(matched), len(rows), change_urgency, change_schemes,
    )
    return matched
