"""Aging analysis for outstanding payables and receivables (HK convention)."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
from typing import Any

from openclaw_shared.database import get_db


def calculate_aging(
    db_path: str | Path, invoice_type: str | None = None
) -> dict[str, Any]:
    """Bucket outstanding invoices by days past due.

    Returns ``{"current": {"total": …, "invoices": […]}, "days_30": …,
    "days_60": …, "days_90_plus": …}``.

    *invoice_type*: ``"payable"``, ``"receivable"``, or ``None`` for both.
    """
    today = date.today()

    conditions = ["i.status NOT IN ('paid', 'written_off')"]
    params: list[Any] = []
    if invoice_type:
        conditions.append("i.invoice_type = ?")
        params.append(invoice_type)

    where = "WHERE " + " AND ".join(conditions)

    query = f"""
        SELECT i.*, c.company_name, c.company_name_tc
        FROM invoices i
        LEFT JOIN contacts c ON c.id = i.contact_id
        {where}
        ORDER BY i.due_date ASC
    """

    with get_db(db_path) as conn:
        rows = conn.execute(query, params).fetchall()

    buckets: dict[str, dict[str, Any]] = {
        "current": {"total": 0.0, "invoices": []},
        "days_30": {"total": 0.0, "invoices": []},
        "days_60": {"total": 0.0, "invoices": []},
        "days_90_plus": {"total": 0.0, "invoices": []},
    }

    for row in rows:
        inv = dict(row)
        due = date.fromisoformat(inv["due_date"]) if inv["due_date"] else today
        days_overdue = (today - due).days
        balance = inv.get("balance", 0.0) or 0.0

        if days_overdue <= 0:
            bucket = "current"
        elif days_overdue <= 30:
            bucket = "days_30"
        elif days_overdue <= 60:
            bucket = "days_60"
        else:
            bucket = "days_90_plus"

        inv["days_overdue"] = max(days_overdue, 0)
        buckets[bucket]["invoices"].append(inv)
        buckets[bucket]["total"] += balance

    return buckets


def get_aging_summary(db_path: str | Path) -> dict[str, Any]:
    """Return aging for both payables and receivables in one call."""
    return {
        "payables_aging": calculate_aging(db_path, invoice_type="payable"),
        "receivables_aging": calculate_aging(db_path, invoice_type="receivable"),
    }
