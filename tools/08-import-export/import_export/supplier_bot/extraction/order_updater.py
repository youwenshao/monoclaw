"""Update orders automatically from extracted message data."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from openclaw_shared.database import get_db

logger = logging.getLogger("openclaw.supplier-bot.order-updater")

STATUS_PROGRESSION = [
    "not_started",
    "in_production",
    "qc_pending",
    "qc_passed",
    "shipping",
    "delivered",
    "completed",
]

ISSUE_TO_STATUS: dict[str, str] = {
    "delay": "in_production",
    "delayed": "in_production",
    "defect": "qc_pending",
    "defective": "qc_pending",
    "reject": "qc_pending",
    "rejected": "qc_pending",
}

DELIVERY_TRIGGERS = {"shipped", "dispatched", "departed", "发货", "出货", "已出"}
ARRIVAL_TRIGGERS = {"arrived", "delivered", "received", "到货", "已到", "签收"}


class OrderUpdater:
    """Apply extracted message data to an existing order."""

    @staticmethod
    def update_from_message(
        db_path: str | Path,
        order_id: int,
        extracted_data: dict[str, Any],
    ) -> dict[str, Any]:
        """Update order fields based on extracted info and return a change summary."""
        changes: dict[str, Any] = {}

        with get_db(db_path) as conn:
            row = conn.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
        if not row:
            return {"order_id": order_id, "error": "not_found"}

        order = dict(row)

        if extracted_data.get("dates"):
            latest_date = extracted_data["dates"][-1]
            if order["expected_delivery"] != latest_date:
                changes["expected_delivery"] = latest_date

        if extracted_data.get("delivery_update"):
            delivery_text = extracted_data["delivery_update"].lower()
            if any(t in delivery_text for t in DELIVERY_TRIGGERS):
                if STATUS_PROGRESSION.index(order["production_status"]) < STATUS_PROGRESSION.index("shipping"):
                    changes["production_status"] = "shipping"
            elif any(t in delivery_text for t in ARRIVAL_TRIGGERS):
                if STATUS_PROGRESSION.index(order["production_status"]) < STATUS_PROGRESSION.index("delivered"):
                    changes["production_status"] = "delivered"

        suggested = OrderUpdater.suggest_status_change(
            order["production_status"], extracted_data
        )
        if suggested and "production_status" not in changes:
            changes["production_status"] = suggested

        if changes:
            set_clauses = [f"{k} = ?" for k in changes]
            params = list(changes.values()) + [order_id]
            with get_db(db_path) as conn:
                conn.execute(
                    f"UPDATE orders SET {', '.join(set_clauses)} WHERE id = ?",  # noqa: S608
                    params,
                )
            logger.info("Order #%d updated: %s", order_id, changes)

        return {"order_id": order_id, "changes": changes, "applied": bool(changes)}

    @staticmethod
    def suggest_status_change(
        current_status: str,
        extracted_data: dict[str, Any],
    ) -> str | None:
        """Suggest a new production status based on extracted message content.

        Returns ``None`` when no status change is warranted.
        """
        if current_status not in STATUS_PROGRESSION:
            return None
        current_idx = STATUS_PROGRESSION.index(current_status)

        issues = extracted_data.get("issues", [])
        for issue in issues:
            mapped = ISSUE_TO_STATUS.get(issue.lower())
            if mapped:
                mapped_idx = STATUS_PROGRESSION.index(mapped)
                if mapped_idx != current_idx:
                    return mapped

        delivery_update = (extracted_data.get("delivery_update") or "").lower()

        if any(kw in delivery_update for kw in ("qc pass", "质检通过", "qc_passed", "inspection passed")):
            if current_idx < STATUS_PROGRESSION.index("qc_passed"):
                return "qc_passed"

        if any(kw in delivery_update for kw in ("in production", "producing", "生产中", "开始生产")):
            if current_idx < STATUS_PROGRESSION.index("in_production"):
                return "in_production"

        if any(kw in delivery_update for kw in ("qc", "inspection", "质检", "验货")):
            if current_idx < STATUS_PROGRESSION.index("qc_pending"):
                return "qc_pending"

        return None
