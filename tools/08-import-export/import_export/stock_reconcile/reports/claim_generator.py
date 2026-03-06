"""Generate carrier / insurance claim documentation from discrepancies."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from openclaw_shared.database import get_db


class ClaimGenerator:
    """Produces claim data and PDF stubs for shipment discrepancies."""

    @staticmethod
    def generate_claim(db_path: str, shipment_id: int) -> dict[str, Any]:
        with get_db(db_path) as conn:
            shipment = conn.execute(
                "SELECT * FROM shipments WHERE id = ?", (shipment_id,)
            ).fetchone()
            if not shipment:
                raise ValueError(f"Shipment {shipment_id} not found")

            discrepancies = conn.execute(
                """SELECT rr.*,
                          mi.item_description AS manifest_description,
                          mi.sku, mi.weight_kg,
                          ri.item_description AS receipt_description,
                          ri.condition, ri.damage_notes
                   FROM reconciliation_results rr
                   LEFT JOIN manifest_items mi ON rr.manifest_item_id = mi.id
                   LEFT JOIN receipt_items ri ON rr.receipt_item_id = ri.id
                   WHERE rr.shipment_id = ? AND rr.status != 'matched'
                   ORDER BY ABS(rr.variance) DESC""",
                (shipment_id,),
            ).fetchall()

        if not discrepancies:
            return {
                "shipment_id": shipment_id,
                "status": "no_discrepancies",
                "message": "No discrepancies found — no claim needed",
            }

        shipment_dict = dict(shipment)
        disc_list = [dict(d) for d in discrepancies]

        claim_items: list[dict[str, Any]] = []
        total_claimed_qty = 0.0
        total_claimed_weight = 0.0

        for d in disc_list:
            variance = abs(d.get("variance") or 0)
            weight = d.get("weight_kg") or 0
            manifest_qty = d.get("quantity_manifest") or 0

            weight_per_unit = weight / manifest_qty if manifest_qty else 0
            claimed_weight = variance * weight_per_unit

            claim_items.append({
                "description": d.get("manifest_description") or d.get("receipt_description") or "Unknown item",
                "sku": d.get("sku"),
                "discrepancy_type": d["status"],
                "manifest_qty": d.get("quantity_manifest"),
                "received_qty": d.get("quantity_received"),
                "variance": d.get("variance"),
                "claimed_qty": variance,
                "claimed_weight_kg": round(claimed_weight, 2),
                "condition": d.get("condition"),
                "damage_notes": d.get("damage_notes"),
            })
            total_claimed_qty += variance
            total_claimed_weight += claimed_weight

        claim = {
            "shipment_id": shipment_id,
            "shipment_reference": shipment_dict.get("shipment_reference"),
            "bl_number": shipment_dict.get("bl_number"),
            "vessel": shipment_dict.get("vessel_name"),
            "voyage": shipment_dict.get("voyage"),
            "consignee": shipment_dict.get("consignee"),
            "carrier": shipment_dict.get("vessel_name"),
            "claim_date": datetime.now().strftime("%Y-%m-%d"),
            "total_discrepancies": len(claim_items),
            "total_claimed_qty": round(total_claimed_qty, 2),
            "total_claimed_weight_kg": round(total_claimed_weight, 2),
            "items": claim_items,
            "status": "draft",
        }

        return claim

    @staticmethod
    def to_pdf(claim: dict[str, Any], output_path: str) -> str:
        """Generate claim PDF. Uses basic text file as stub if reportlab unavailable."""
        try:
            from reportlab.lib.pagesizes import A4
            from reportlab.lib.units import mm
            from reportlab.pdfgen import canvas

            c = canvas.Canvas(output_path, pagesize=A4)
            width, height = A4
            y = height - 30 * mm

            c.setFont("Helvetica-Bold", 16)
            c.drawString(30 * mm, y, "Cargo Discrepancy Claim")
            y -= 12 * mm

            c.setFont("Helvetica", 10)
            fields = [
                ("Claim Date", claim.get("claim_date")),
                ("Shipment Ref", claim.get("shipment_reference")),
                ("B/L Number", claim.get("bl_number")),
                ("Vessel / Voyage", f"{claim.get('vessel', '')} / {claim.get('voyage', '')}"),
                ("Consignee", claim.get("consignee")),
                ("Total Discrepancies", claim.get("total_discrepancies")),
                ("Total Claimed Qty", claim.get("total_claimed_qty")),
                ("Total Claimed Weight (kg)", claim.get("total_claimed_weight_kg")),
            ]

            for label, value in fields:
                c.drawString(30 * mm, y, f"{label}: {value or 'N/A'}")
                y -= 6 * mm

            y -= 6 * mm
            c.setFont("Helvetica-Bold", 11)
            c.drawString(30 * mm, y, "Discrepancy Details")
            y -= 8 * mm

            c.setFont("Helvetica", 9)
            for idx, item in enumerate(claim.get("items", []), 1):
                if y < 30 * mm:
                    c.showPage()
                    y = height - 30 * mm
                    c.setFont("Helvetica", 9)

                c.drawString(30 * mm, y, f"{idx}. {item['description']} (SKU: {item.get('sku', 'N/A')})")
                y -= 5 * mm
                c.drawString(35 * mm, y,
                    f"Type: {item['discrepancy_type']} | "
                    f"Manifest: {item['manifest_qty']} | Received: {item['received_qty']} | "
                    f"Variance: {item['variance']}"
                )
                y -= 5 * mm
                if item.get("damage_notes"):
                    c.drawString(35 * mm, y, f"Notes: {item['damage_notes']}")
                    y -= 5 * mm
                y -= 3 * mm

            c.save()

        except ImportError:
            with open(output_path, "w") as f:
                f.write("CARGO DISCREPANCY CLAIM\n")
                f.write("=" * 50 + "\n\n")
                f.write(f"Claim Date: {claim.get('claim_date')}\n")
                f.write(f"Shipment: {claim.get('shipment_reference')}\n")
                f.write(f"B/L: {claim.get('bl_number')}\n")
                f.write(f"Vessel/Voyage: {claim.get('vessel')} / {claim.get('voyage')}\n")
                f.write(f"Consignee: {claim.get('consignee')}\n\n")
                f.write(f"Total Discrepancies: {claim.get('total_discrepancies')}\n")
                f.write(f"Total Claimed Qty: {claim.get('total_claimed_qty')}\n")
                f.write(f"Total Claimed Weight: {claim.get('total_claimed_weight_kg')} kg\n\n")
                f.write("ITEMS:\n")
                f.write("-" * 50 + "\n")
                for idx, item in enumerate(claim.get("items", []), 1):
                    f.write(f"\n{idx}. {item['description']} (SKU: {item.get('sku', 'N/A')})\n")
                    f.write(f"   Type: {item['discrepancy_type']}\n")
                    f.write(f"   Manifest Qty: {item['manifest_qty']} → Received: {item['received_qty']}\n")
                    f.write(f"   Variance: {item['variance']}\n")
                    if item.get("damage_notes"):
                        f.write(f"   Damage Notes: {item['damage_notes']}\n")

        return output_path
