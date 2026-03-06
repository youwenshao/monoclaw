"""Duplicate invoice detection.

Checks for potential duplicates by matching on invoice_number, supplier_name,
and total_amount. A combination match on any two fields is considered a
potential duplicate; all three matching is a strong duplicate.
"""

from __future__ import annotations

from typing import Any

from openclaw_shared.database import get_db


def check_duplicate(
    invoice_number: str | None,
    supplier_name: str | None,
    total_amount: float | None,
    db_path: str,
    exclude_id: int | None = None,
) -> dict[str, Any]:
    """Check if an invoice is a potential duplicate.

    Returns dict with:
        is_duplicate: bool
        confidence: 'strong' | 'possible' | None
        matches: list of matching invoice IDs with match details
    """
    result: dict[str, Any] = {
        "is_duplicate": False,
        "confidence": None,
        "matches": [],
    }

    if not any([invoice_number, supplier_name, total_amount]):
        return result

    with get_db(db_path) as conn:
        candidates = conn.execute(
            "SELECT id, invoice_number, supplier_name, total_amount, invoice_date, status "
            "FROM invoices WHERE status != 'rejected'"
        ).fetchall()

    for row in candidates:
        cand = dict(row)
        cand_id = cand["id"]

        if exclude_id is not None and cand_id == exclude_id:
            continue

        match_fields: list[str] = []

        if invoice_number and cand.get("invoice_number"):
            if invoice_number.strip().lower() == cand["invoice_number"].strip().lower():
                match_fields.append("invoice_number")

        if supplier_name and cand.get("supplier_name"):
            if supplier_name.strip().lower() == cand["supplier_name"].strip().lower():
                match_fields.append("supplier_name")

        if total_amount is not None and cand.get("total_amount") is not None:
            if abs(total_amount - cand["total_amount"]) < 0.01:
                match_fields.append("total_amount")

        if len(match_fields) >= 2:
            confidence = "strong" if len(match_fields) >= 3 else "possible"
            result["matches"].append({
                "invoice_id": cand_id,
                "matched_fields": match_fields,
                "confidence": confidence,
                "invoice_number": cand.get("invoice_number"),
                "supplier_name": cand.get("supplier_name"),
                "total_amount": cand.get("total_amount"),
                "status": cand.get("status"),
            })

    if result["matches"]:
        result["is_duplicate"] = True
        result["confidence"] = (
            "strong" if any(m["confidence"] == "strong" for m in result["matches"])
            else "possible"
        )

    return result
