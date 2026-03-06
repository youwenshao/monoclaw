"""Work order creation from defect records."""

from __future__ import annotations

import logging
from datetime import date
from pathlib import Path

from openclaw_shared.database import get_db

logger = logging.getLogger("openclaw.construction.defects_manager.work_orders.generator")


def create_work_order_from_defect(
    db_path: str | Path,
    defect_id: int,
    contractor_id: int | None = None,
    scope: str = "",
) -> int:
    """Create a work order linked to an existing defect.

    Returns the new work order ID, or ``-1`` if the defect was not found.
    """
    with get_db(db_path) as conn:
        defect = conn.execute("SELECT * FROM defects WHERE id = ?", (defect_id,)).fetchone()
        if not defect:
            logger.warning("Cannot create work order — defect #%d not found", defect_id)
            return -1

        if not scope:
            scope = (
                f"Repair {defect['category'].replace('_', ' ')} defect at "
                f"{defect['floor']}F / Unit {defect['unit']}. "
                f"Description: {defect['description']}"
            )

        cursor = conn.execute(
            "INSERT INTO work_orders "
            "(defect_id, contractor_id, scope_of_work, issue_date, status) "
            "VALUES (?, ?, ?, ?, ?)",
            (defect_id, contractor_id, scope, date.today().isoformat(), "draft"),
        )
        wo_id: int = cursor.lastrowid  # type: ignore[assignment]

        conn.execute(
            "UPDATE defects SET status = 'work_ordered' WHERE id = ?",
            (defect_id,),
        )

        conn.execute(
            "INSERT INTO defect_updates (defect_id, update_type, description, updated_by) "
            "VALUES (?, ?, ?, ?)",
            (defect_id, "work_order", f"Work order #{wo_id} created", "system"),
        )

    logger.info("Work order #%d created for defect #%d", wo_id, defect_id)
    return wo_id
