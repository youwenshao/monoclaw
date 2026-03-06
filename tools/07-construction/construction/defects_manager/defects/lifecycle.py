"""Defect status lifecycle management.

Valid transitions::

    reported -> assessed -> work_ordered -> in_progress -> completed -> closed
    reported -> referred
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

from openclaw_shared.database import get_db

logger = logging.getLogger("openclaw.construction.defects_manager.defects.lifecycle")

VALID_TRANSITIONS: dict[str, list[str]] = {
    "reported": ["assessed", "referred"],
    "assessed": ["work_ordered", "referred"],
    "work_ordered": ["in_progress"],
    "in_progress": ["completed"],
    "completed": ["closed"],
    "referred": [],
    "closed": [],
}


def transition_status(
    db_path: str | Path,
    defect_id: int,
    new_status: str,
    updated_by: str = "",
) -> bool:
    """Attempt to transition a defect to *new_status*.

    Returns ``True`` if the transition succeeded, ``False`` if it was invalid
    or the defect was not found.  Creates a ``defect_updates`` record on
    success.
    """
    with get_db(db_path) as conn:
        row = conn.execute("SELECT status FROM defects WHERE id = ?", (defect_id,)).fetchone()
        if not row:
            logger.warning("Defect #%d not found", defect_id)
            return False

        current = row["status"]
        allowed = VALID_TRANSITIONS.get(current, [])

        if new_status not in allowed:
            logger.warning(
                "Invalid transition for defect #%d: %s -> %s (allowed: %s)",
                defect_id, current, new_status, allowed,
            )
            return False

        now = datetime.now().isoformat()
        updates = ["status = ?"]
        params: list[str | int] = [new_status]

        if new_status == "closed":
            updates.append("closed_date = ?")
            params.append(now)

        params.append(defect_id)
        conn.execute(f"UPDATE defects SET {', '.join(updates)} WHERE id = ?", params)

        conn.execute(
            "INSERT INTO defect_updates (defect_id, update_type, description, updated_by, updated_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (defect_id, "status_change", f"{current} -> {new_status}", updated_by or "system", now),
        )

    logger.info("Defect #%d transitioned %s -> %s", defect_id, current, new_status)
    return True
