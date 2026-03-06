"""Priority assessment and auto-escalation for defects."""

from __future__ import annotations

import logging
from pathlib import Path

from openclaw_shared.database import get_db

logger = logging.getLogger("openclaw.construction.defects_manager.defects.priority_engine")

EMERGENCY_CATEGORIES = {"structural", "electrical", "lift"}
URGENT_CATEGORIES = {"water_seepage", "concrete_spalling"}

SAFETY_KEYWORDS = [
    "collapse", "fire", "electrocution", "gas", "falling", "dangerous",
    "injury", "hazard", "urgent", "emergency", "immediate",
    "倒塌", "火警", "觸電", "危險", "緊急",
]


def assess_priority(category: str, description: str) -> str:
    """Determine priority level based on category and description.

    Returns one of: ``emergency``, ``urgent``, ``high``, ``normal``, ``low``.
    """
    lower_desc = description.lower()

    if any(kw in lower_desc for kw in SAFETY_KEYWORDS):
        return "emergency"

    if category in EMERGENCY_CATEGORIES:
        if any(kw in lower_desc for kw in ("stuck", "trapped", "no power", "sparking")):
            return "emergency"
        return "urgent"

    if category in URGENT_CATEGORIES:
        return "urgent"

    if category == "plumbing" and any(kw in lower_desc for kw in ("flood", "burst", "overflow")):
        return "urgent"

    return "normal"


def auto_escalate(db_path: str | Path, defect_id: int, category: str) -> None:
    """Re-assess and update a defect's priority if warranted.

    Called automatically after defect creation in ``routes.py``.
    """
    with get_db(db_path) as conn:
        row = conn.execute("SELECT * FROM defects WHERE id = ?", (defect_id,)).fetchone()
        if not row:
            logger.warning("Defect #%d not found for auto-escalation", defect_id)
            return

        description = row["description"] or ""
        current_priority = row["priority"] or "normal"

        new_priority = assess_priority(category, description)

        priority_rank = {"emergency": 4, "urgent": 3, "high": 2, "normal": 1, "low": 0}
        if priority_rank.get(new_priority, 0) > priority_rank.get(current_priority, 0):
            conn.execute(
                "UPDATE defects SET priority = ? WHERE id = ?",
                (new_priority, defect_id),
            )
            conn.execute(
                "INSERT INTO defect_updates (defect_id, update_type, description, updated_by) "
                "VALUES (?, ?, ?, ?)",
                (defect_id, "escalation", f"Auto-escalated to {new_priority} (category: {category})", "system"),
            )
            logger.info("Defect #%d escalated from %s to %s", defect_id, current_priority, new_priority)
