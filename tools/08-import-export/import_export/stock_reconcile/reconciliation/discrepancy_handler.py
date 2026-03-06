"""Categorize, query, and summarize reconciliation discrepancies."""

from __future__ import annotations

from typing import Any

from openclaw_shared.database import get_db


class DiscrepancyHandler:
    """Handles discrepancy classification, querying, and summary generation."""

    @staticmethod
    def categorize(manifest_qty: float, received_qty: float, condition: str = "good") -> str:
        if condition.lower() in ("damaged", "partial"):
            return "damaged"
        variance = received_qty - manifest_qty
        if abs(variance) < 0.001:
            return "matched"
        return "shortage" if variance < 0 else "overage"

    @staticmethod
    def get_discrepancies(db_path: str, shipment_id: int | None = None) -> list[dict[str, Any]]:
        query = """
            SELECT rr.id, rr.shipment_id, rr.manifest_item_id, rr.receipt_item_id,
                   rr.match_confidence, rr.quantity_manifest, rr.quantity_received,
                   rr.variance, rr.status, rr.notes, rr.reconciled_at,
                   s.shipment_reference, s.bl_number, s.vessel_name,
                   mi.item_description AS manifest_description, mi.sku AS manifest_sku,
                   ri.item_description AS receipt_description, ri.sku AS receipt_sku,
                   ri.condition, ri.damage_notes
            FROM reconciliation_results rr
            JOIN shipments s ON rr.shipment_id = s.id
            LEFT JOIN manifest_items mi ON rr.manifest_item_id = mi.id
            LEFT JOIN receipt_items ri ON rr.receipt_item_id = ri.id
            WHERE rr.status != 'matched'
        """
        params: list[Any] = []

        if shipment_id is not None:
            query += " AND rr.shipment_id = ?"
            params.append(shipment_id)

        query += " ORDER BY ABS(rr.variance) DESC"

        with get_db(db_path) as conn:
            rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]

    @staticmethod
    def generate_discrepancy_summary(results: list[dict[str, Any]]) -> dict[str, Any]:
        summary: dict[str, Any] = {
            "total_discrepancies": 0,
            "by_category": {"shortage": 0, "overage": 0, "damaged": 0, "unmatched_manifest": 0, "unmatched_receipt": 0},
            "total_shortage_qty": 0.0,
            "total_overage_qty": 0.0,
            "items_with_damage": 0,
        }

        for r in results:
            status = r.get("status", "")
            if status == "matched":
                continue

            summary["total_discrepancies"] += 1
            if status in summary["by_category"]:
                summary["by_category"][status] += 1

            variance = r.get("variance") or 0
            if status == "shortage":
                summary["total_shortage_qty"] += abs(variance)
            elif status == "overage":
                summary["total_overage_qty"] += variance

            if status == "damaged":
                summary["items_with_damage"] += 1

        return summary
