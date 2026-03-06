"""Track container and shipment status through the reconciliation lifecycle."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from openclaw_shared.database import get_db


class ContainerTracker:
    """Manages shipment status transitions and container-based lookups."""

    VALID_STATUSES = ("in_transit", "arrived", "gate_out", "at_warehouse", "reconciled", "closed")

    def update_status(self, db_path: str, shipment_id: int, status: str) -> dict[str, Any]:
        if status not in self.VALID_STATUSES:
            raise ValueError(f"Invalid status '{status}'. Must be one of {self.VALID_STATUSES}")

        with get_db(db_path) as conn:
            row = conn.execute("SELECT * FROM shipments WHERE id = ?", (shipment_id,)).fetchone()
            if not row:
                raise ValueError(f"Shipment {shipment_id} not found")

            old_status = row["status"]
            conn.execute(
                "UPDATE shipments SET status = ? WHERE id = ?",
                (status, shipment_id),
            )

        return {
            "shipment_id": shipment_id,
            "old_status": old_status,
            "new_status": status,
            "updated_at": datetime.now().isoformat(),
        }

    @staticmethod
    def get_container_history(db_path: str, container_number: str) -> list[dict[str, Any]]:
        with get_db(db_path) as conn:
            rows = conn.execute(
                """SELECT id, shipment_reference, bl_number, vessel_name,
                          voyage, origin_port, arrival_date, container_numbers,
                          load_type, consignee, status, created_at
                   FROM shipments
                   WHERE container_numbers LIKE ?
                   ORDER BY created_at DESC""",
                (f"%{container_number}%",),
            ).fetchall()
        return [dict(r) for r in rows]

    @staticmethod
    def get_active_shipments(db_path: str) -> list[dict[str, Any]]:
        with get_db(db_path) as conn:
            rows = conn.execute(
                """SELECT s.id, s.shipment_reference, s.bl_number, s.vessel_name,
                          s.voyage, s.origin_port, s.arrival_date,
                          s.container_numbers, s.load_type, s.consignee,
                          s.status, s.created_at,
                          COUNT(mi.id) AS manifest_item_count,
                          (SELECT COUNT(*) FROM warehouse_receipts wr
                           WHERE wr.shipment_id = s.id) AS receipt_count
                   FROM shipments s
                   LEFT JOIN manifest_items mi ON mi.shipment_id = s.id
                   WHERE s.status NOT IN ('closed', 'reconciled')
                   GROUP BY s.id
                   ORDER BY s.created_at DESC"""
            ).fetchall()
        return [dict(r) for r in rows]
