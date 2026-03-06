"""Predict collection likelihood based on customer payment history."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

from openclaw_shared.database import get_db


def predict_collection_likelihood(
    db_path: str | Path, invoice_id: int
) -> dict[str, Any]:
    """Estimate the probability that a receivable will be collected.

    Uses the customer's historical payment behaviour: average days to pay
    and on-time rate.  Returns ``{"probability": 0–1, "based_on": {…}}``.
    """
    with get_db(db_path) as conn:
        inv = conn.execute(
            "SELECT contact_id, due_date, balance, total_amount FROM invoices WHERE id = ?",
            (invoice_id,),
        ).fetchone()

    if not inv:
        return {"probability": 0.0, "based_on": {"error": "Invoice not found"}}

    inv = dict(inv)
    contact_id = inv["contact_id"]
    history = get_customer_payment_history(db_path, contact_id)

    past_invoices = history["total_invoices"]
    on_time_rate = history["on_time_rate"]
    avg_days = history["avg_days_to_pay"]

    if past_invoices == 0:
        probability = 0.5
        reason = "No payment history — default estimate"
    else:
        base = on_time_rate
        if inv.get("due_date"):
            try:
                days_overdue = (date.today() - date.fromisoformat(inv["due_date"])).days
            except ValueError:
                days_overdue = 0
        else:
            days_overdue = 0

        if days_overdue > 90:
            penalty = 0.4
        elif days_overdue > 60:
            penalty = 0.25
        elif days_overdue > 30:
            penalty = 0.1
        else:
            penalty = 0.0

        probability = max(0.05, min(1.0, base - penalty))
        reason = (
            f"Based on {past_invoices} past invoices, "
            f"{on_time_rate:.0%} on-time rate, "
            f"avg {avg_days:.0f} days to pay"
        )
        if days_overdue > 0:
            reason += f", currently {days_overdue}d overdue"

    return {
        "probability": round(probability, 2),
        "based_on": {
            "total_past_invoices": past_invoices,
            "on_time_rate": on_time_rate,
            "avg_days_to_pay": avg_days,
            "explanation": reason,
        },
    }


def get_customer_payment_history(
    db_path: str | Path, contact_id: int
) -> dict[str, Any]:
    """Analyse a customer's payment behaviour.

    Returns ``{"avg_days_to_pay": float, "on_time_rate": float,
    "total_invoices": int, "paid_invoices": int}``.
    """
    with get_db(db_path) as conn:
        rows = conn.execute(
            """SELECT i.id, i.due_date, i.status,
                      MIN(p.payment_date) as first_payment_date
               FROM invoices i
               LEFT JOIN payments p ON p.invoice_id = i.id
               WHERE i.contact_id = ? AND i.invoice_type = 'receivable'
               GROUP BY i.id""",
            (contact_id,),
        ).fetchall()

    total = 0
    paid = 0
    on_time = 0
    days_list: list[int] = []

    for row in rows:
        r = dict(row)
        total += 1
        if r["status"] in ("paid", "partially_paid"):
            paid += 1
        if r.get("first_payment_date") and r.get("due_date"):
            try:
                pay_d = date.fromisoformat(r["first_payment_date"])
                due_d = date.fromisoformat(r["due_date"])
                days_to_pay = (pay_d - due_d).days
                days_list.append(days_to_pay)
                if days_to_pay <= 0:
                    on_time += 1
            except ValueError:
                pass

    avg_days = sum(days_list) / len(days_list) if days_list else 0.0
    on_time_rate = on_time / total if total > 0 else 0.0

    return {
        "avg_days_to_pay": round(avg_days, 1),
        "on_time_rate": round(on_time_rate, 2),
        "total_invoices": total,
        "paid_invoices": paid,
    }
