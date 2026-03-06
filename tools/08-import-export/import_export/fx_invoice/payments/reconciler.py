"""Bank payment reconciliation and auto-matching."""

from __future__ import annotations

from openclaw_shared.database import get_db


class BankReconciler:

    def match_payment(
        self, db_path: str, bank_reference: str, amount: float, currency: str
    ) -> list[dict]:
        """Find invoices that match a bank payment by reference or amount."""
        with get_db(db_path) as conn:
            by_ref = conn.execute(
                """SELECT i.* FROM invoices i
                   JOIN payments p ON p.invoice_id = i.id
                   WHERE p.bank_reference = ?""",
                (bank_reference,),
            ).fetchall()

            if by_ref:
                return [dict(r) for r in by_ref]

            by_amount = conn.execute(
                """SELECT * FROM invoices
                   WHERE currency = ?
                     AND status IN ('sent', 'partially_paid', 'overdue')
                     AND ABS(total - ?) < 0.01
                   ORDER BY due_date""",
                (currency, amount),
            ).fetchall()

            if by_amount:
                return [dict(r) for r in by_amount]

            partial = conn.execute(
                """SELECT i.*, (i.total - COALESCE(
                       (SELECT SUM(p.amount) FROM payments p WHERE p.invoice_id = i.id), 0
                   )) as outstanding
                   FROM invoices i
                   WHERE i.currency = ?
                     AND i.status IN ('sent', 'partially_paid', 'overdue')
                   HAVING ABS(outstanding - ?) < 0.01
                   ORDER BY i.due_date""",
                (currency, amount),
            ).fetchall()

            return [dict(r) for r in partial]

    def suggest_matches(
        self, db_path: str, payments: list[dict]
    ) -> list[dict]:
        """Auto-suggest invoice matches for a batch of bank payments."""
        suggestions = []
        for pmt in payments:
            ref = pmt.get("bank_reference", "")
            amount = pmt.get("amount", 0)
            currency = pmt.get("currency", "HKD")

            matches = self.match_payment(db_path, ref, amount, currency)
            confidence = 0.0
            if matches:
                first = matches[0]
                if abs(first.get("total", 0) - amount) < 0.01:
                    confidence = 0.95
                else:
                    confidence = 0.70

            suggestions.append({
                "payment": pmt,
                "matches": matches,
                "confidence": confidence,
                "auto_match": confidence >= 0.90,
            })

        return suggestions
