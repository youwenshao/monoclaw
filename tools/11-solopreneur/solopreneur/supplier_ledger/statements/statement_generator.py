"""Generate monthly account statements for contacts."""

from __future__ import annotations

import calendar
from datetime import date
from pathlib import Path
from typing import Any

from openclaw_shared.database import get_db


def generate_monthly_statement(
    db_path: str | Path, contact_id: int, year: int, month: int
) -> dict[str, Any]:
    """Build a statement dict for one contact covering a calendar month.

    Returns ``{"contact": {…}, "opening_balance": …, "transactions": […],
    "closing_balance": …, "period_start": …, "period_end": …}``.
    """
    first_day = date(year, month, 1)
    last_day = date(year, month, calendar.monthrange(year, month)[1])
    period_start = first_day.isoformat()
    period_end = last_day.isoformat()

    with get_db(db_path) as conn:
        contact_row = conn.execute(
            "SELECT * FROM contacts WHERE id = ?", (contact_id,)
        ).fetchone()
        if not contact_row:
            return {"error": "Contact not found"}
        contact = dict(contact_row)

        opening_row = conn.execute(
            """SELECT COALESCE(SUM(
                   CASE WHEN invoice_type = 'receivable' THEN balance ELSE -balance END
               ), 0) as bal
               FROM invoices
               WHERE contact_id = ? AND invoice_date < ?
                 AND status NOT IN ('written_off')""",
            (contact_id, period_start),
        ).fetchone()
        opening_balance = opening_row["bal"]

        invoices = [
            dict(r)
            for r in conn.execute(
                """SELECT id, invoice_type, invoice_number, invoice_date,
                          due_date, total_amount, balance, status
                   FROM invoices
                   WHERE contact_id = ? AND invoice_date BETWEEN ? AND ?
                   ORDER BY invoice_date""",
                (contact_id, period_start, period_end),
            ).fetchall()
        ]

        payments_rows = conn.execute(
            """SELECT p.id, p.invoice_id, p.payment_date, p.amount,
                      p.payment_method, i.invoice_number
               FROM payments p
               JOIN invoices i ON i.id = p.invoice_id
               WHERE i.contact_id = ? AND p.payment_date BETWEEN ? AND ?
               ORDER BY p.payment_date""",
            (contact_id, period_start, period_end),
        ).fetchall()
        payments = [dict(r) for r in payments_rows]

    transactions: list[dict[str, Any]] = []
    for inv in invoices:
        sign = 1 if inv["invoice_type"] == "receivable" else -1
        transactions.append({
            "date": inv["invoice_date"],
            "type": "invoice",
            "reference": inv["invoice_number"] or f"INV-{inv['id']}",
            "description": f"Invoice ({inv['invoice_type']})",
            "amount": inv["total_amount"] * sign,
        })

    for pmt in payments:
        transactions.append({
            "date": pmt["payment_date"],
            "type": "payment",
            "reference": pmt["invoice_number"] or f"PMT-{pmt['id']}",
            "description": f"Payment ({pmt['payment_method']})",
            "amount": -pmt["amount"],
        })

    transactions.sort(key=lambda t: t["date"])

    running = opening_balance
    for txn in transactions:
        running += txn["amount"]
        txn["running_balance"] = round(running, 2)

    closing_balance = round(running, 2)

    with get_db(db_path) as conn:
        conn.execute(
            """INSERT INTO statements
               (contact_id, statement_date, opening_balance, closing_balance, status)
               VALUES (?,?,?,?,?)""",
            (contact_id, period_end, opening_balance, closing_balance, "generated"),
        )

    return {
        "contact": contact,
        "opening_balance": round(opening_balance, 2),
        "transactions": transactions,
        "closing_balance": closing_balance,
        "period_start": period_start,
        "period_end": period_end,
    }


def generate_all_statements(
    db_path: str | Path, year: int, month: int
) -> list[dict[str, Any]]:
    """Generate statements for every active contact with activity in the period."""
    with get_db(db_path) as conn:
        contacts = conn.execute(
            "SELECT id FROM contacts WHERE active = 1"
        ).fetchall()

    results: list[dict[str, Any]] = []
    for row in contacts:
        stmt = generate_monthly_statement(db_path, row["id"], year, month)
        if stmt.get("transactions"):
            results.append(stmt)
    return results
