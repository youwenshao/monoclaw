"""Monthly statement and outstanding balance calculations."""

from __future__ import annotations

from openclaw_shared.database import get_db


class StatementGenerator:

    def generate_monthly_statement(
        self, db_path: str, customer_id: int, year: int, month: int
    ) -> dict:
        """Aggregate invoices and payments for a customer in a given month."""
        month_start = f"{year}-{month:02d}-01"
        if month == 12:
            month_end = f"{year + 1}-01-01"
        else:
            month_end = f"{year}-{month + 1:02d}-01"

        with get_db(db_path) as conn:
            invoices = [
                dict(r)
                for r in conn.execute(
                    """SELECT * FROM invoices
                       WHERE customer_id = ?
                         AND invoice_date >= ? AND invoice_date < ?
                       ORDER BY invoice_date""",
                    (customer_id, month_start, month_end),
                ).fetchall()
            ]

            payments = [
                dict(r)
                for r in conn.execute(
                    """SELECT p.* FROM payments p
                       JOIN invoices i ON p.invoice_id = i.id
                       WHERE i.customer_id = ?
                         AND p.payment_date >= ? AND p.payment_date < ?
                       ORDER BY p.payment_date""",
                    (customer_id, month_start, month_end),
                ).fetchall()
            ]

            customer = conn.execute(
                "SELECT * FROM customers WHERE id = ?", (customer_id,)
            ).fetchone()

        total_invoiced = sum(inv.get("total", 0) for inv in invoices)
        total_invoiced_hkd = sum(inv.get("hkd_equivalent", 0) for inv in invoices)
        total_paid = sum(pmt.get("amount", 0) for pmt in payments)
        total_paid_hkd = sum(pmt.get("hkd_equivalent", 0) for pmt in payments)
        total_fx_gain_loss = sum(pmt.get("fx_gain_loss", 0) for pmt in payments)

        return {
            "customer": dict(customer) if customer else None,
            "period": f"{year}-{month:02d}",
            "invoices": invoices,
            "payments": payments,
            "summary": {
                "total_invoiced": round(total_invoiced, 2),
                "total_invoiced_hkd": round(total_invoiced_hkd, 2),
                "total_paid": round(total_paid, 2),
                "total_paid_hkd": round(total_paid_hkd, 2),
                "net_outstanding": round(total_invoiced - total_paid, 2),
                "net_outstanding_hkd": round(total_invoiced_hkd - total_paid_hkd, 2),
                "fx_gain_loss": round(total_fx_gain_loss, 2),
            },
        }

    def get_outstanding_balance(self, db_path: str, customer_id: int) -> dict:
        """Return outstanding balance per currency with HKD equivalent."""
        with get_db(db_path) as conn:
            rows = conn.execute(
                """SELECT currency,
                          SUM(total) as total_amount,
                          SUM(hkd_equivalent) as total_hkd
                   FROM invoices
                   WHERE customer_id = ?
                     AND status IN ('sent', 'partially_paid', 'overdue')
                   GROUP BY currency""",
                (customer_id,),
            ).fetchall()

            paid_rows = conn.execute(
                """SELECT i.currency,
                          SUM(p.amount) as paid_amount,
                          SUM(p.hkd_equivalent) as paid_hkd
                   FROM payments p
                   JOIN invoices i ON p.invoice_id = i.id
                   WHERE i.customer_id = ?
                     AND i.status IN ('sent', 'partially_paid', 'overdue')
                   GROUP BY i.currency""",
                (customer_id,),
            ).fetchall()

        invoiced = {r["currency"]: {"amount": r["total_amount"], "hkd": r["total_hkd"]} for r in rows}
        paid = {r["currency"]: {"amount": r["paid_amount"], "hkd": r["paid_hkd"]} for r in paid_rows}

        balances = {}
        total_hkd = 0.0
        for currency, inv in invoiced.items():
            p = paid.get(currency, {"amount": 0, "hkd": 0})
            outstanding = round(inv["amount"] - p["amount"], 2)
            outstanding_hkd = round(inv["hkd"] - p["hkd"], 2)
            balances[currency] = {
                "outstanding": outstanding,
                "hkd_equivalent": outstanding_hkd,
            }
            total_hkd += outstanding_hkd

        return {
            "customer_id": customer_id,
            "balances": balances,
            "total_hkd": round(total_hkd, 2),
        }
