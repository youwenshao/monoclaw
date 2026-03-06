"""Invoice creation and numbering logic."""

from __future__ import annotations

from datetime import date, datetime, timedelta

from openclaw_shared.database import get_db


class InvoiceGenerator:

    def create_invoice(self, db_path: str, data: dict) -> dict:
        """Create an invoice with auto-generated number and HKD equivalent."""
        prefix = data.get("prefix", "INV")
        invoice_number = self.get_next_invoice_number(db_path, prefix)
        items = data.get("items", [])
        totals = self.calculate_totals(items)

        fx_rate = data.get("fx_rate", 1.0)
        hkd_equivalent = totals["total"] * fx_rate if data.get("currency", "HKD") != "HKD" else totals["total"]

        invoice_date = data.get("invoice_date", date.today().isoformat())
        due_date = data.get("due_date")
        if not due_date:
            payment_terms = data.get("payment_terms_days", 30)
            due_dt = datetime.fromisoformat(invoice_date) + timedelta(days=payment_terms)
            due_date = due_dt.date().isoformat()

        with get_db(db_path) as conn:
            cursor = conn.execute(
                """INSERT INTO invoices
                   (invoice_number, customer_id, invoice_type, invoice_date, due_date,
                    currency, subtotal, total, hkd_equivalent, fx_rate_used,
                    fx_rate_date, payment_method, status, notes)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    invoice_number,
                    data.get("customer_id"),
                    data.get("invoice_type", "sales"),
                    invoice_date,
                    due_date,
                    data.get("currency", "HKD"),
                    totals["subtotal"],
                    totals["total"],
                    round(hkd_equivalent, 2),
                    fx_rate,
                    data.get("fx_rate_date", date.today().isoformat()),
                    data.get("payment_method", "T/T"),
                    "draft",
                    data.get("notes"),
                ),
            )
            invoice_id = cursor.lastrowid

        if items:
            self.add_line_items(db_path, invoice_id, items)

        return {
            "id": invoice_id,
            "invoice_number": invoice_number,
            "subtotal": totals["subtotal"],
            "total": totals["total"],
            "hkd_equivalent": round(hkd_equivalent, 2),
            "status": "draft",
        }

    def get_next_invoice_number(self, db_path: str, prefix: str = "INV") -> str:
        """Generate next sequential number like INV-2026-0003."""
        year = date.today().year
        pattern = f"{prefix}-{year}-%"

        with get_db(db_path) as conn:
            row = conn.execute(
                "SELECT invoice_number FROM invoices WHERE invoice_number LIKE ? ORDER BY id DESC LIMIT 1",
                (pattern,),
            ).fetchone()

        if row:
            last_seq = int(row[0].rsplit("-", 1)[-1])
            next_seq = last_seq + 1
        else:
            next_seq = 1

        return f"{prefix}-{year}-{next_seq:04d}"

    def add_line_items(self, db_path: str, invoice_id: int, items: list[dict]) -> None:
        """Insert line items for an invoice."""
        with get_db(db_path) as conn:
            for item in items:
                amount = round(item.get("quantity", 1) * item.get("unit_price", 0), 2)
                conn.execute(
                    """INSERT INTO invoice_items
                       (invoice_id, description, quantity, unit_price, amount, hs_code, notes)
                       VALUES (?,?,?,?,?,?,?)""",
                    (
                        invoice_id,
                        item.get("description", ""),
                        item.get("quantity", 1),
                        item.get("unit_price", 0),
                        amount,
                        item.get("hs_code"),
                        item.get("notes"),
                    ),
                )

    def calculate_totals(self, items: list[dict]) -> dict:
        """Calculate subtotal and total from line items."""
        subtotal = sum(
            round(item.get("quantity", 1) * item.get("unit_price", 0), 2)
            for item in items
        )
        return {"subtotal": round(subtotal, 2), "total": round(subtotal, 2)}
