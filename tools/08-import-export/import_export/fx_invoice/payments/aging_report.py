"""Accounts receivable aging report generator."""

from __future__ import annotations

from datetime import date, timedelta

from openclaw_shared.database import get_db


class AgingReport:

    def generate(self, db_path: str, as_of_date: date | None = None) -> dict:
        """Generate aging buckets: current, 30, 60, 90+ days."""
        as_of = as_of_date or date.today()

        with get_db(db_path) as conn:
            invoices = [
                dict(r)
                for r in conn.execute(
                    """SELECT i.*,
                              c.company_name as customer_name,
                              COALESCE(
                                  (SELECT SUM(p.amount) FROM payments p WHERE p.invoice_id = i.id), 0
                              ) as paid_amount
                       FROM invoices i
                       LEFT JOIN customers c ON i.customer_id = c.id
                       WHERE i.status IN ('sent', 'partially_paid', 'overdue')"""
                ).fetchall()
            ]

        buckets = {
            "current": [],
            "30_days": [],
            "60_days": [],
            "90_plus": [],
        }
        totals = {
            "current": {"amount": 0.0, "hkd": 0.0},
            "30_days": {"amount": 0.0, "hkd": 0.0},
            "60_days": {"amount": 0.0, "hkd": 0.0},
            "90_plus": {"amount": 0.0, "hkd": 0.0},
        }

        for inv in invoices:
            outstanding = (inv.get("total", 0) or 0) - (inv.get("paid_amount", 0) or 0)
            if outstanding <= 0:
                continue

            due_date_str = inv.get("due_date", "")
            if not due_date_str:
                continue
            due_date = date.fromisoformat(due_date_str)
            days_past = (as_of - due_date).days

            fx_rate = inv.get("fx_rate_used", 1.0) or 1.0
            outstanding_hkd = round(outstanding * fx_rate, 2)

            entry = {
                "invoice_id": inv["id"],
                "invoice_number": inv.get("invoice_number"),
                "customer_name": inv.get("customer_name"),
                "currency": inv.get("currency"),
                "outstanding": round(outstanding, 2),
                "outstanding_hkd": outstanding_hkd,
                "due_date": due_date_str,
                "days_past_due": max(days_past, 0),
            }

            if days_past <= 0:
                bucket = "current"
            elif days_past <= 30:
                bucket = "30_days"
            elif days_past <= 60:
                bucket = "60_days"
            else:
                bucket = "90_plus"

            buckets[bucket].append(entry)
            totals[bucket]["amount"] += outstanding
            totals[bucket]["hkd"] += outstanding_hkd

        for key in totals:
            totals[key]["amount"] = round(totals[key]["amount"], 2)
            totals[key]["hkd"] = round(totals[key]["hkd"], 2)

        grand_total_hkd = sum(t["hkd"] for t in totals.values())

        return {
            "as_of_date": as_of.isoformat(),
            "buckets": buckets,
            "totals": totals,
            "grand_total_hkd": round(grand_total_hkd, 2),
        }

    def get_customer_aging(self, db_path: str, customer_id: int) -> dict:
        """Generate aging report filtered to a single customer."""
        as_of = date.today()

        with get_db(db_path) as conn:
            invoices = [
                dict(r)
                for r in conn.execute(
                    """SELECT i.*,
                              COALESCE(
                                  (SELECT SUM(p.amount) FROM payments p WHERE p.invoice_id = i.id), 0
                              ) as paid_amount
                       FROM invoices i
                       WHERE i.customer_id = ?
                         AND i.status IN ('sent', 'partially_paid', 'overdue')""",
                    (customer_id,),
                ).fetchall()
            ]

        buckets: dict[str, float] = {"current": 0.0, "30_days": 0.0, "60_days": 0.0, "90_plus": 0.0}
        buckets_hkd: dict[str, float] = {"current": 0.0, "30_days": 0.0, "60_days": 0.0, "90_plus": 0.0}

        for inv in invoices:
            outstanding = (inv.get("total", 0) or 0) - (inv.get("paid_amount", 0) or 0)
            if outstanding <= 0:
                continue

            due_date_str = inv.get("due_date", "")
            if not due_date_str:
                continue
            due_date = date.fromisoformat(due_date_str)
            days_past = (as_of - due_date).days
            fx_rate = inv.get("fx_rate_used", 1.0) or 1.0

            if days_past <= 0:
                bucket = "current"
            elif days_past <= 30:
                bucket = "30_days"
            elif days_past <= 60:
                bucket = "60_days"
            else:
                bucket = "90_plus"

            buckets[bucket] += outstanding
            buckets_hkd[bucket] += outstanding * fx_rate

        for key in buckets:
            buckets[key] = round(buckets[key], 2)
            buckets_hkd[key] = round(buckets_hkd[key], 2)

        return {
            "customer_id": customer_id,
            "as_of_date": as_of.isoformat(),
            "buckets": buckets,
            "buckets_hkd": buckets_hkd,
            "total_hkd": round(sum(buckets_hkd.values()), 2),
        }
