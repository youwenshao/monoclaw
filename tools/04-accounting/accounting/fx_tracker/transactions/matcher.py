"""FX settlement matching using FIFO queue consumption."""

from __future__ import annotations

import logging
from datetime import date
from pathlib import Path
from typing import Any

from openclaw_shared.database import get_db

logger = logging.getLogger("openclaw.accounting.fx.matcher")


def settle_transaction(
    tx_id: int,
    settlement_rate: float,
    settled_date: date | str,
    db_path: str | Path,
    method: str = "fifo",
) -> dict[str, Any]:
    """Settle an FX transaction and calculate realized gain/loss.

    Args:
        tx_id: Transaction to settle.
        settlement_rate: The actual rate at settlement.
        settled_date: Date of settlement.
        db_path: Path to the fx_tracker database.
        method: "fifo" (default) or "weighted_average".

    Returns:
        Dict with tx_id, realized_gain_loss, settlement details.
    """
    if isinstance(settled_date, str):
        settled_date = date.fromisoformat(settled_date)

    with get_db(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM fx_transactions WHERE id = ?", (tx_id,)
        ).fetchone()

    if not row:
        raise ValueError(f"Transaction #{tx_id} not found")

    tx = dict(row)
    if tx["is_settled"]:
        raise ValueError(f"Transaction #{tx_id} is already settled")

    if method == "fifo":
        gain_loss = _settle_fifo(tx, settlement_rate)
    elif method == "weighted_average":
        gain_loss = _settle_weighted_average(tx, settlement_rate, db_path)
    else:
        raise ValueError(f"Unknown settlement method: {method}")

    settlement_hkd = round(tx["foreign_amount"] * settlement_rate, 2)

    with get_db(db_path) as conn:
        conn.execute(
            """UPDATE fx_transactions SET
                is_settled = 1,
                settled_date = ?,
                settlement_rate = ?,
                settlement_hkd = ?,
                realized_gain_loss = ?
               WHERE id = ?""",
            (
                settled_date.isoformat(),
                settlement_rate,
                settlement_hkd,
                gain_loss,
                tx_id,
            ),
        )

    logger.info(
        "Settled tx #%d (%s): rate %.4f -> %.4f, G/L = HKD %.2f",
        tx_id, tx["currency"], tx["exchange_rate"], settlement_rate, gain_loss,
    )

    return {
        "tx_id": tx_id,
        "currency": tx["currency"],
        "foreign_amount": tx["foreign_amount"],
        "original_rate": tx["exchange_rate"],
        "settlement_rate": settlement_rate,
        "settlement_hkd": settlement_hkd,
        "realized_gain_loss": gain_loss,
        "settled_date": settled_date.isoformat(),
        "method": method,
    }


def _settle_fifo(tx: dict[str, Any], settlement_rate: float) -> float:
    """Calculate realized gain/loss using FIFO.

    For a receivable: gain if settlement rate > original rate (received more HKD).
    For a payable: gain if settlement rate < original rate (paid less HKD).
    """
    foreign_amount = tx["foreign_amount"]
    original_rate = tx["exchange_rate"]
    tx_type = tx["transaction_type"]

    original_hkd = foreign_amount * original_rate
    settled_hkd = foreign_amount * settlement_rate

    if tx_type == "receivable":
        gain_loss = settled_hkd - original_hkd
    else:
        gain_loss = original_hkd - settled_hkd

    return round(gain_loss, 2)


def _settle_weighted_average(
    tx: dict[str, Any],
    settlement_rate: float,
    db_path: str | Path,
) -> float:
    """Calculate realized gain/loss using weighted-average cost.

    Looks up all settled transactions for the same currency to compute
    the weighted-average original rate, then compares to settlement.
    """
    currency = tx["currency"]
    tx_type = tx["transaction_type"]

    with get_db(db_path) as conn:
        rows = conn.execute(
            """SELECT foreign_amount, exchange_rate
               FROM fx_transactions
               WHERE currency = ? AND transaction_type = ? AND is_settled = 1""",
            (currency, tx_type),
        ).fetchall()

    total_foreign = sum(r["foreign_amount"] for r in rows) + tx["foreign_amount"]
    total_hkd = sum(r["foreign_amount"] * r["exchange_rate"] for r in rows) + (
        tx["foreign_amount"] * tx["exchange_rate"]
    )

    if total_foreign == 0:
        return 0.0

    weighted_avg_rate = total_hkd / total_foreign
    settled_hkd = tx["foreign_amount"] * settlement_rate
    original_hkd = tx["foreign_amount"] * weighted_avg_rate

    if tx_type == "receivable":
        gain_loss = settled_hkd - original_hkd
    else:
        gain_loss = original_hkd - settled_hkd

    return round(gain_loss, 2)


def batch_settle(
    tx_ids: list[int],
    settlement_rate: float,
    settled_date: date | str,
    db_path: str | Path,
    method: str = "fifo",
) -> list[dict[str, Any]]:
    """Settle multiple transactions at the same rate (e.g. a single wire receipt)."""
    results = []
    for tx_id in tx_ids:
        try:
            result = settle_transaction(tx_id, settlement_rate, settled_date, db_path, method)
            results.append(result)
        except ValueError as exc:
            logger.warning("Skipping tx #%d: %s", tx_id, exc)
            results.append({"tx_id": tx_id, "error": str(exc)})
    return results
