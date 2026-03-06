"""FCL (Full Container Load) reconciliation — single consignee per shipment."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from openclaw_shared.database import get_db

from .matching_engine import MatchingEngine


class FCLReconciler:
    """Reconcile a full-container-load shipment: one manifest vs one receipt."""

    def reconcile(
        self,
        db_path: str,
        shipment_id: int,
        matching_engine: MatchingEngine,
    ) -> dict[str, Any]:
        manifest_items = self._load_manifest_items(db_path, shipment_id)
        receipt_items = self._load_receipt_items(db_path, shipment_id)

        if not manifest_items:
            return {
                "shipment_id": shipment_id,
                "status": "error",
                "message": "No manifest items found for this shipment",
                "results": [],
            }

        if not receipt_items:
            return {
                "shipment_id": shipment_id,
                "status": "pending_receipt",
                "message": "No warehouse receipt items found yet",
                "results": [],
            }

        results = matching_engine.match(manifest_items, receipt_items)
        self._store_results(db_path, shipment_id, results)

        with get_db(db_path) as conn:
            conn.execute(
                "UPDATE shipments SET status = 'reconciled' WHERE id = ?",
                (shipment_id,),
            )

        summary = self._summarize(results)
        return {
            "shipment_id": shipment_id,
            "status": "reconciled",
            "total_items": len(results),
            "summary": summary,
            "results": results,
        }

    def _load_manifest_items(self, db_path: str, shipment_id: int) -> list[dict[str, Any]]:
        with get_db(db_path) as conn:
            rows = conn.execute(
                """SELECT id, item_description AS description, sku, quantity,
                          unit, weight_kg, carton_count, container_number
                   FROM manifest_items WHERE shipment_id = ?""",
                (shipment_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    def _load_receipt_items(self, db_path: str, shipment_id: int) -> list[dict[str, Any]]:
        with get_db(db_path) as conn:
            rows = conn.execute(
                """SELECT ri.id, ri.item_description AS description, ri.sku,
                          ri.quantity_received, ri.unit, ri.condition,
                          ri.damage_notes, wr.receipt_number
                   FROM receipt_items ri
                   JOIN warehouse_receipts wr ON ri.receipt_id = wr.id
                   WHERE wr.shipment_id = ?""",
                (shipment_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    def _store_results(
        self,
        db_path: str,
        shipment_id: int,
        results: list[dict[str, Any]],
    ) -> None:
        with get_db(db_path) as conn:
            conn.execute(
                "DELETE FROM reconciliation_results WHERE shipment_id = ?",
                (shipment_id,),
            )

            for r in results:
                m_item = r.get("manifest_item") or {}
                r_item = r.get("receipt_item") or {}
                conn.execute(
                    """INSERT INTO reconciliation_results
                       (shipment_id, manifest_item_id, receipt_item_id,
                        match_confidence, quantity_manifest, quantity_received,
                        variance, status, notes)
                       VALUES (?,?,?,?,?,?,?,?,?)""",
                    (
                        shipment_id,
                        m_item.get("id"),
                        r_item.get("id"),
                        r["match_confidence"],
                        m_item.get("quantity"),
                        r_item.get("quantity_received"),
                        r["variance"],
                        r["status"],
                        r.get("match_method"),
                    ),
                )

    @staticmethod
    def _summarize(results: list[dict[str, Any]]) -> dict[str, int]:
        summary: dict[str, int] = {
            "matched": 0, "shortage": 0, "overage": 0,
            "damaged": 0, "unmatched_manifest": 0, "unmatched_receipt": 0,
        }
        for r in results:
            status = r.get("status", "matched")
            summary[status] = summary.get(status, 0) + 1
        return summary
