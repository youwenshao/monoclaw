"""LCL (Less-than Container Load) reconciliation — multiple consignees per container."""

from __future__ import annotations

from typing import Any

from openclaw_shared.database import get_db

from .matching_engine import MatchingEngine


class LCLReconciler:
    """Reconcile an LCL shipment grouped by House B/L (one per consignee)."""

    def reconcile(
        self,
        db_path: str,
        shipment_id: int,
        matching_engine: MatchingEngine,
    ) -> dict[str, Any]:
        house_bls = self._get_house_bls(db_path, shipment_id)

        if not house_bls:
            from .fcl_reconciler import FCLReconciler
            return FCLReconciler().reconcile(db_path, shipment_id, matching_engine)

        all_results: list[dict[str, Any]] = []
        consignee_summaries: list[dict[str, Any]] = []

        for hbl in house_bls:
            hbl_id = hbl["id"]
            manifest_items = self._load_manifest_for_hbl(db_path, hbl_id)
            receipt_items = self._load_receipt_for_hbl(db_path, hbl_id)

            if not manifest_items:
                consignee_summaries.append({
                    "house_bl": hbl["bl_number"],
                    "consignee": hbl["consignee"],
                    "status": "no_manifest",
                    "items": 0,
                })
                continue

            if not receipt_items:
                consignee_summaries.append({
                    "house_bl": hbl["bl_number"],
                    "consignee": hbl["consignee"],
                    "status": "pending_receipt",
                    "items": len(manifest_items),
                })
                continue

            results = matching_engine.match(manifest_items, receipt_items)
            all_results.extend(results)

            summary = self._count_statuses(results)
            consignee_summaries.append({
                "house_bl": hbl["bl_number"],
                "consignee": hbl["consignee"],
                "status": "reconciled",
                "items": len(results),
                "summary": summary,
            })

        self._store_results(db_path, shipment_id, all_results)

        with get_db(db_path) as conn:
            conn.execute(
                "UPDATE shipments SET status = 'reconciled' WHERE id = ?",
                (shipment_id,),
            )

        return {
            "shipment_id": shipment_id,
            "load_type": "LCL",
            "status": "reconciled",
            "house_bls": len(house_bls),
            "total_items": len(all_results),
            "consignees": consignee_summaries,
            "results": all_results,
        }

    def _get_house_bls(self, db_path: str, shipment_id: int) -> list[dict[str, Any]]:
        with get_db(db_path) as conn:
            parent = conn.execute(
                "SELECT bl_number FROM shipments WHERE id = ?", (shipment_id,)
            ).fetchone()
            if not parent:
                return []

            rows = conn.execute(
                """SELECT id, bl_number, consignee
                   FROM shipments
                   WHERE master_bl = ? AND bl_type = 'house'
                   ORDER BY id""",
                (parent["bl_number"],),
            ).fetchall()
        return [dict(r) for r in rows]

    def _load_manifest_for_hbl(self, db_path: str, hbl_shipment_id: int) -> list[dict[str, Any]]:
        with get_db(db_path) as conn:
            rows = conn.execute(
                """SELECT id, item_description AS description, sku, quantity,
                          unit, weight_kg, carton_count
                   FROM manifest_items WHERE shipment_id = ?""",
                (hbl_shipment_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    def _load_receipt_for_hbl(self, db_path: str, hbl_shipment_id: int) -> list[dict[str, Any]]:
        with get_db(db_path) as conn:
            rows = conn.execute(
                """SELECT ri.id, ri.item_description AS description, ri.sku,
                          ri.quantity_received, ri.unit, ri.condition, ri.damage_notes
                   FROM receipt_items ri
                   JOIN warehouse_receipts wr ON ri.receipt_id = wr.id
                   WHERE wr.shipment_id = ?""",
                (hbl_shipment_id,),
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
    def _count_statuses(results: list[dict[str, Any]]) -> dict[str, int]:
        counts: dict[str, int] = {}
        for r in results:
            s = r.get("status", "matched")
            counts[s] = counts.get(s, 0) + 1
        return counts
