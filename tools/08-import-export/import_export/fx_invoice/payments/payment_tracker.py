"""Payment recording with FX gain/loss calculation."""

from __future__ import annotations

from openclaw_shared.database import get_db


class PaymentTracker:

    def record_payment(self, db_path: str, payment_data: dict) -> dict:
        """Record a payment, calculate FX gain/loss, and update invoice status."""
        invoice_id = payment_data["invoice_id"]
        amount = payment_data["amount"]
        fx_rate_at_payment = payment_data.get("fx_rate_at_payment", 1.0)

        with get_db(db_path) as conn:
            inv = conn.execute(
                "SELECT * FROM invoices WHERE id = ?", (invoice_id,)
            ).fetchone()
            if not inv:
                raise ValueError(f"Invoice {invoice_id} not found")
            invoice = dict(inv)

        invoice_rate = invoice.get("fx_rate_used", 1.0)
        fx_gain_loss = self.calculate_fx_gain_loss(invoice_rate, fx_rate_at_payment, amount)
        hkd_equivalent = round(amount * fx_rate_at_payment, 2)

        with get_db(db_path) as conn:
            cursor = conn.execute(
                """INSERT INTO payments
                   (invoice_id, payment_date, amount, currency,
                    fx_rate_at_payment, hkd_equivalent, payment_method,
                    bank_reference, fx_gain_loss, notes)
                   VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (
                    invoice_id,
                    payment_data.get("payment_date"),
                    amount,
                    payment_data.get("currency", invoice["currency"]),
                    fx_rate_at_payment,
                    hkd_equivalent,
                    payment_data.get("payment_method", "T/T"),
                    payment_data.get("bank_reference"),
                    fx_gain_loss,
                    payment_data.get("notes"),
                ),
            )
            payment_id = cursor.lastrowid

            outstanding = self.get_outstanding_amount(db_path, invoice_id)
            if outstanding <= 0.005:
                new_status = "paid"
            else:
                new_status = "partially_paid"
            conn.execute(
                "UPDATE invoices SET status = ? WHERE id = ?",
                (new_status, invoice_id),
            )

        return {
            "payment_id": payment_id,
            "invoice_id": invoice_id,
            "amount": amount,
            "hkd_equivalent": hkd_equivalent,
            "fx_gain_loss": fx_gain_loss,
            "invoice_status": new_status,
        }

    @staticmethod
    def calculate_fx_gain_loss(
        invoice_rate: float, payment_rate: float, amount: float
    ) -> float:
        """Calculate FX gain/loss: positive = gain, negative = loss.

        gain_loss = amount * (payment_rate - invoice_rate)
        A higher payment rate means more HKD received per unit = gain.
        """
        return round(amount * (payment_rate - invoice_rate), 2)

    def get_invoice_payments(self, db_path: str, invoice_id: int) -> list[dict]:
        """List all payments for an invoice."""
        with get_db(db_path) as conn:
            rows = conn.execute(
                "SELECT * FROM payments WHERE invoice_id = ? ORDER BY payment_date",
                (invoice_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    def get_outstanding_amount(self, db_path: str, invoice_id: int) -> float:
        """Calculate remaining unpaid amount for an invoice."""
        with get_db(db_path) as conn:
            inv = conn.execute(
                "SELECT total FROM invoices WHERE id = ?", (invoice_id,)
            ).fetchone()
            if not inv:
                return 0.0

            paid_row = conn.execute(
                "SELECT COALESCE(SUM(amount), 0) FROM payments WHERE invoice_id = ?",
                (invoice_id,),
            ).fetchone()

        total = inv["total"] or 0.0
        paid = paid_row[0] if paid_row else 0.0
        return round(max(total - paid, 0), 2)
