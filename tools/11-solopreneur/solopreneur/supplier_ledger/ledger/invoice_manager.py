"""Invoice CRUD and status management for payables/receivables."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from openclaw_shared.database import get_db


def create_invoice(db_path: str | Path, data: dict[str, Any]) -> dict[str, Any]:
    """Create a new invoice and return it.

    *data* keys: contact_id, invoice_type, invoice_number, invoice_date,
    currency (optional, default HKD), total_amount, notes, pdf_path.
    ``due_date`` is auto-computed from the contact's ``payment_terms_days``
    when not explicitly provided.
    """
    contact_id = data["contact_id"]
    invoice_date_str = data.get("invoice_date", date.today().isoformat())
    total_amount = float(data["total_amount"])

    with get_db(db_path) as conn:
        contact = conn.execute(
            "SELECT payment_terms_days FROM contacts WHERE id = ?", (contact_id,)
        ).fetchone()
        terms = (dict(contact) if contact else {}).get("payment_terms_days", 30) or 30

    due_date_str = data.get("due_date")
    if not due_date_str:
        inv_date = date.fromisoformat(invoice_date_str)
        due_date_str = (inv_date + timedelta(days=terms)).isoformat()

    balance = total_amount

    with get_db(db_path) as conn:
        cursor = conn.execute(
            """INSERT INTO invoices
               (contact_id, invoice_type, invoice_number, invoice_date,
                due_date, currency, total_amount, paid_amount, balance,
                status, pdf_path, notes)
               VALUES (?,?,?,?,?,?,?,0,?,?,?,?)""",
            (
                contact_id,
                data["invoice_type"],
                data.get("invoice_number", ""),
                invoice_date_str,
                due_date_str,
                data.get("currency", "HKD"),
                total_amount,
                balance,
                "outstanding",
                data.get("pdf_path"),
                data.get("notes"),
            ),
        )
        inv_id = cursor.lastrowid

    return get_invoice(db_path, inv_id)  # type: ignore[arg-type]


def get_invoices(
    db_path: str | Path,
    invoice_type: str | None = None,
    status: str | None = None,
    contact_id: int | None = None,
) -> list[dict[str, Any]]:
    """Retrieve invoices with optional filters, newest first."""
    conditions: list[str] = []
    params: list[Any] = []

    if invoice_type:
        conditions.append("i.invoice_type = ?")
        params.append(invoice_type)
    if status:
        conditions.append("i.status = ?")
        params.append(status)
    if contact_id is not None:
        conditions.append("i.contact_id = ?")
        params.append(contact_id)

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    query = f"""
        SELECT i.*, c.company_name, c.company_name_tc
        FROM invoices i
        LEFT JOIN contacts c ON c.id = i.contact_id
        {where}
        ORDER BY i.invoice_date DESC
    """

    with get_db(db_path) as conn:
        rows = conn.execute(query, params).fetchall()
    return [dict(r) for r in rows]


def get_invoice(db_path: str | Path, invoice_id: int) -> dict[str, Any] | None:
    """Return a single invoice joined with contact info."""
    with get_db(db_path) as conn:
        row = conn.execute(
            """SELECT i.*, c.company_name, c.company_name_tc
               FROM invoices i
               LEFT JOIN contacts c ON c.id = i.contact_id
               WHERE i.id = ?""",
            (invoice_id,),
        ).fetchone()
    return dict(row) if row else None


def update_invoice_status(db_path: str | Path, invoice_id: int) -> None:
    """Recalculate an invoice's paid_amount, balance, and status."""
    with get_db(db_path) as conn:
        inv = conn.execute(
            "SELECT total_amount, due_date FROM invoices WHERE id = ?",
            (invoice_id,),
        ).fetchone()
        if not inv:
            return

        inv = dict(inv)
        paid_row = conn.execute(
            "SELECT COALESCE(SUM(amount), 0) as paid FROM payments WHERE invoice_id = ?",
            (invoice_id,),
        ).fetchone()
        paid_amount = paid_row["paid"]
        balance = inv["total_amount"] - paid_amount

        if balance <= 0:
            status = "paid"
            balance = 0.0
        elif paid_amount > 0:
            status = "partially_paid"
        elif inv["due_date"] and date.fromisoformat(inv["due_date"]) < date.today():
            status = "overdue"
        else:
            status = "outstanding"

        conn.execute(
            "UPDATE invoices SET paid_amount = ?, balance = ?, status = ? WHERE id = ?",
            (paid_amount, balance, status, invoice_id),
        )


def get_overdue_invoices(db_path: str | Path) -> list[dict[str, Any]]:
    """Return all invoices past their due date that are not fully paid."""
    today = date.today().isoformat()
    with get_db(db_path) as conn:
        rows = conn.execute(
            """SELECT i.*, c.company_name, c.company_name_tc, c.phone, c.whatsapp, c.email
               FROM invoices i
               LEFT JOIN contacts c ON c.id = i.contact_id
               WHERE i.due_date < ? AND i.status NOT IN ('paid', 'written_off')
               ORDER BY i.due_date ASC""",
            (today,),
        ).fetchall()
    return [dict(r) for r in rows]


def get_outstanding_totals(db_path: str | Path) -> dict[str, float]:
    """Return aggregate outstanding payables and receivables."""
    with get_db(db_path) as conn:
        payable = conn.execute(
            "SELECT COALESCE(SUM(balance), 0) FROM invoices WHERE invoice_type = 'payable' AND status NOT IN ('paid', 'written_off')"
        ).fetchone()[0]
        receivable = conn.execute(
            "SELECT COALESCE(SUM(balance), 0) FROM invoices WHERE invoice_type = 'receivable' AND status NOT IN ('paid', 'written_off')"
        ).fetchone()[0]
    return {"payables_total": payable, "receivables_total": receivable}
