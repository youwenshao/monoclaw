"""Realized FX gain/loss calculation.

Supports both FIFO lot consumption and weighted-average cost methods.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from openclaw_shared.database import get_db

logger = logging.getLogger("openclaw.accounting.fx.realized")


def calculate_realized_gain_loss(
    original_rate: float,
    settlement_rate: float,
    foreign_amount: float,
    transaction_type: str,
) -> dict[str, Any]:
    """Calculate realized FX gain/loss for a single position.

    For receivables, a gain occurs when settlement_rate > original_rate
    (client receives more HKD than originally booked).

    For payables, a gain occurs when settlement_rate < original_rate
    (client pays less HKD than originally booked).
    """
    original_hkd = round(foreign_amount * original_rate, 2)
    settled_hkd = round(foreign_amount * settlement_rate, 2)

    if transaction_type == "receivable":
        gain_loss = settled_hkd - original_hkd
    else:
        gain_loss = original_hkd - settled_hkd

    gain_loss = round(gain_loss, 2)

    return {
        "original_rate": original_rate,
        "settlement_rate": settlement_rate,
        "foreign_amount": foreign_amount,
        "original_hkd": original_hkd,
        "settled_hkd": settled_hkd,
        "gain_loss": gain_loss,
        "direction": "gain" if gain_loss >= 0 else "loss",
    }


def calculate_fifo_gain_loss(
    currency: str,
    settlement_amount: float,
    settlement_rate: float,
    transaction_type: str,
    db_path: str | Path,
) -> dict[str, Any]:
    """Calculate realized G/L by consuming lots in FIFO order.

    Walks through unsettled transactions for the given currency (oldest first)
    and consumes foreign_amount lots until settlement_amount is exhausted.
    Returns the total realized gain/loss and per-lot breakdown.
    """
    currency = currency.upper()
    remaining = settlement_amount
    lots_consumed: list[dict[str, Any]] = []
    total_gain_loss = 0.0

    with get_db(db_path) as conn:
        rows = conn.execute(
            """SELECT id, foreign_amount, exchange_rate, transaction_date
               FROM fx_transactions
               WHERE currency = ? AND transaction_type = ? AND is_settled = 0
               ORDER BY transaction_date ASC, id ASC""",
            (currency, transaction_type),
        ).fetchall()

    for row in rows:
        if remaining <= 0:
            break

        lot = dict(row)
        lot_amount = lot["foreign_amount"]
        consumed = min(lot_amount, remaining)
        lot_rate = lot["exchange_rate"]

        lot_result = calculate_realized_gain_loss(
            original_rate=lot_rate,
            settlement_rate=settlement_rate,
            foreign_amount=consumed,
            transaction_type=transaction_type,
        )

        lots_consumed.append({
            "tx_id": lot["id"],
            "transaction_date": lot["transaction_date"],
            "consumed_amount": consumed,
            "lot_rate": lot_rate,
            **lot_result,
        })

        total_gain_loss += lot_result["gain_loss"]
        remaining -= consumed

    return {
        "method": "fifo",
        "currency": currency,
        "settlement_amount": settlement_amount,
        "settlement_rate": settlement_rate,
        "lots_consumed": lots_consumed,
        "total_gain_loss": round(total_gain_loss, 2),
        "unconsumed_remainder": round(remaining, 2),
    }


def calculate_weighted_average_gain_loss(
    currency: str,
    settlement_amount: float,
    settlement_rate: float,
    transaction_type: str,
    db_path: str | Path,
) -> dict[str, Any]:
    """Calculate realized G/L using weighted-average cost basis.

    Computes the average exchange rate across all unsettled positions for
    the currency and uses that as the original rate for comparison.
    """
    currency = currency.upper()

    with get_db(db_path) as conn:
        row = conn.execute(
            """SELECT SUM(foreign_amount) as total_foreign,
                      SUM(hkd_amount) as total_hkd
               FROM fx_transactions
               WHERE currency = ? AND transaction_type = ? AND is_settled = 0""",
            (currency, transaction_type),
        ).fetchone()

    total_foreign = row["total_foreign"] or 0.0
    total_hkd = row["total_hkd"] or 0.0

    if total_foreign == 0:
        return {
            "method": "weighted_average",
            "currency": currency,
            "settlement_amount": settlement_amount,
            "settlement_rate": settlement_rate,
            "weighted_avg_rate": 0.0,
            "total_gain_loss": 0.0,
        }

    weighted_avg_rate = total_hkd / total_foreign

    result = calculate_realized_gain_loss(
        original_rate=weighted_avg_rate,
        settlement_rate=settlement_rate,
        foreign_amount=settlement_amount,
        transaction_type=transaction_type,
    )

    return {
        "method": "weighted_average",
        "currency": currency,
        "settlement_amount": settlement_amount,
        "settlement_rate": settlement_rate,
        "weighted_avg_rate": round(weighted_avg_rate, 6),
        **result,
    }


def summarize_realized_by_currency(db_path: str | Path) -> list[dict[str, Any]]:
    """Aggregate realized gains/losses by currency for reporting."""
    with get_db(db_path) as conn:
        rows = conn.execute(
            """SELECT
                currency,
                COUNT(*) as transaction_count,
                SUM(foreign_amount) as total_foreign,
                SUM(hkd_amount) as total_original_hkd,
                SUM(settlement_hkd) as total_settlement_hkd,
                SUM(realized_gain_loss) as total_realized
               FROM fx_transactions
               WHERE is_settled = 1 AND realized_gain_loss IS NOT NULL
               GROUP BY currency
               ORDER BY currency"""
        ).fetchall()

    return [
        {
            "currency": r["currency"],
            "transaction_count": r["transaction_count"],
            "total_foreign": r["total_foreign"],
            "total_original_hkd": round(r["total_original_hkd"], 2),
            "total_settlement_hkd": round(r["total_settlement_hkd"] or 0, 2),
            "total_realized": round(r["total_realized"], 2),
        }
        for r in rows
    ]
