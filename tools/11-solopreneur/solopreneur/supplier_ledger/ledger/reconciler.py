"""Bank statement import and auto-reconciliation."""

from __future__ import annotations

import csv
import io
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from openclaw_shared.database import get_db


def import_bank_statement(
    db_path: str | Path, csv_content: str, bank_name: str
) -> dict[str, Any]:
    """Parse a bank CSV and insert rows into ``bank_transactions``.

    Expected CSV columns (flexible order): Date, Description, Amount.
    Returns counts of imported and auto-matched transactions.
    """
    reader = csv.DictReader(io.StringIO(csv_content))
    imported = 0

    with get_db(db_path) as conn:
        for row in reader:
            txn_date = _normalise_date(
                row.get("Date") or row.get("date") or row.get("Transaction Date") or ""
            )
            description = (
                row.get("Description") or row.get("description") or row.get("Narrative") or ""
            )
            amount_str = (
                row.get("Amount") or row.get("amount") or row.get("Debit")
                or row.get("Credit") or "0"
            )
            amount = float(amount_str.replace(",", "").replace("$", ""))

            conn.execute(
                """INSERT INTO bank_transactions
                   (transaction_date, description, amount, bank_name)
                   VALUES (?,?,?,?)""",
                (txn_date, description.strip(), amount, bank_name),
            )
            imported += 1

    result = auto_reconcile(db_path)
    result["imported_count"] = imported
    return result


def auto_reconcile(db_path: str | Path) -> dict[str, int]:
    """Try to match unmatched bank transactions to invoices.

    Strategy:
    1. Exact amount match on an outstanding invoice.
    2. Amount match within a +-3 day window around invoice date / due date.
    """
    matched = 0
    unmatched = 0

    with get_db(db_path) as conn:
        txns = conn.execute(
            "SELECT * FROM bank_transactions WHERE match_status = 'unmatched'"
        ).fetchall()

        for txn in txns:
            txn = dict(txn)
            amt = abs(txn["amount"])

            exact = conn.execute(
                """SELECT id FROM invoices
                   WHERE ABS(balance - ?) < 0.01
                     AND status NOT IN ('paid', 'written_off')
                   LIMIT 1""",
                (amt,),
            ).fetchone()

            if exact:
                conn.execute(
                    "UPDATE bank_transactions SET matched_invoice_id = ?, match_status = 'matched' WHERE id = ?",
                    (exact["id"], txn["id"]),
                )
                matched += 1
                continue

            txn_date = txn.get("transaction_date")
            if txn_date:
                try:
                    td = date.fromisoformat(txn_date)
                except ValueError:
                    td = None
            else:
                td = None

            if td:
                window_start = (td - timedelta(days=3)).isoformat()
                window_end = (td + timedelta(days=3)).isoformat()
                date_match = conn.execute(
                    """SELECT id FROM invoices
                       WHERE ABS(balance - ?) < 0.01
                         AND status NOT IN ('paid', 'written_off')
                         AND (invoice_date BETWEEN ? AND ? OR due_date BETWEEN ? AND ?)
                       LIMIT 1""",
                    (amt, window_start, window_end, window_start, window_end),
                ).fetchone()

                if date_match:
                    conn.execute(
                        "UPDATE bank_transactions SET matched_invoice_id = ?, match_status = 'matched' WHERE id = ?",
                        (date_match["id"], txn["id"]),
                    )
                    matched += 1
                    continue

            unmatched += 1

    return {"matched_count": matched, "unmatched_count": unmatched}


def match_transaction(
    db_path: str | Path, bank_txn_id: int, invoice_id: int
) -> dict[str, Any]:
    """Manually match a bank transaction to an invoice."""
    with get_db(db_path) as conn:
        conn.execute(
            "UPDATE bank_transactions SET matched_invoice_id = ?, match_status = 'manual' WHERE id = ?",
            (invoice_id, bank_txn_id),
        )
    return {"bank_txn_id": bank_txn_id, "invoice_id": invoice_id, "status": "manual"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _normalise_date(raw: str) -> str:
    """Best-effort parse DD/MM/YYYY or YYYY-MM-DD into ISO format."""
    raw = raw.strip()
    if not raw:
        return date.today().isoformat()
    if "/" in raw:
        parts = raw.split("/")
        if len(parts) == 3:
            if len(parts[0]) == 4:  # YYYY/MM/DD
                return f"{parts[0]}-{parts[1].zfill(2)}-{parts[2].zfill(2)}"
            return f"{parts[2]}-{parts[1].zfill(2)}-{parts[0].zfill(2)}"
    return raw
