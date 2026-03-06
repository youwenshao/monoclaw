"""Record and query payments against invoices."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

from openclaw_shared.database import get_db

from solopreneur.supplier_ledger.ledger.invoice_manager import update_invoice_status


def record_payment(
    db_path: str | Path,
    invoice_id: int,
    amount: float,
    payment_method: str,
    cheque_number: str | None = None,
    bank_reference: str | None = None,
    notes: str | None = None,
) -> dict[str, Any]:
    """Insert a payment and refresh the parent invoice status.

    Returns the newly created payment row.
    """
    payment_date = date.today().isoformat()

    with get_db(db_path) as conn:
        cursor = conn.execute(
            """INSERT INTO payments
               (invoice_id, payment_date, amount, payment_method,
                cheque_number, bank_reference, notes)
               VALUES (?,?,?,?,?,?,?)""",
            (invoice_id, payment_date, amount, payment_method,
             cheque_number, bank_reference, notes),
        )
        payment_id = cursor.lastrowid

    update_invoice_status(db_path, invoice_id)

    with get_db(db_path) as conn:
        row = conn.execute("SELECT * FROM payments WHERE id = ?", (payment_id,)).fetchone()
    return dict(row) if row else {"id": payment_id}


def get_payments_for_invoice(
    db_path: str | Path, invoice_id: int
) -> list[dict[str, Any]]:
    """Return all payments linked to a given invoice, newest first."""
    with get_db(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM payments WHERE invoice_id = ? ORDER BY payment_date DESC",
            (invoice_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def get_recent_payments(
    db_path: str | Path, limit: int = 50
) -> list[dict[str, Any]]:
    """Return the most recent payments across all invoices."""
    with get_db(db_path) as conn:
        rows = conn.execute(
            """SELECT p.*, i.invoice_number, i.invoice_type,
                      c.company_name, c.company_name_tc
               FROM payments p
               LEFT JOIN invoices i ON i.id = p.invoice_id
               LEFT JOIN contacts c ON c.id = i.contact_id
               ORDER BY p.recorded_at DESC
               LIMIT ?""",
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]
