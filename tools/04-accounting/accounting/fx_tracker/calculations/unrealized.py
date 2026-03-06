"""Unrealized FX gain/loss calculation at closing rate."""

from __future__ import annotations

import logging
from datetime import date
from pathlib import Path
from typing import Any

from openclaw_shared.database import get_db

logger = logging.getLogger("openclaw.accounting.fx.unrealized")


def calculate_unrealized_gains(
    period_end_date: str | date,
    db_path: str | Path,
) -> list[dict[str, Any]]:
    """Calculate unrealized FX gains/losses for all open positions at closing rate.

    For each unsettled transaction, retrieves the closing rate as of period_end_date
    and computes the difference from the booked rate:
    - Receivable: unrealized G/L = (closing_rate - original_rate) * foreign_amount
    - Payable:    unrealized G/L = (original_rate - closing_rate) * foreign_amount

    Results are persisted to the revaluations table.
    """
    if isinstance(period_end_date, str):
        period_end_date = date.fromisoformat(period_end_date)

    from accounting.fx_tracker.rates.cache import get_closing_rate

    with get_db(db_path) as conn:
        positions = [dict(r) for r in conn.execute(
            """SELECT id, client_id, currency, foreign_amount, exchange_rate,
                      hkd_amount, transaction_type
               FROM fx_transactions
               WHERE is_settled = 0
               ORDER BY transaction_date"""
        ).fetchall()]

    if not positions:
        return []

    results: list[dict[str, Any]] = []

    for pos in positions:
        currency = pos["currency"]
        closing = get_closing_rate(period_end_date, currency, db_path)

        if closing is None:
            logger.warning(
                "No closing rate for %s at %s — skipping tx #%d",
                currency, period_end_date, pos["id"],
            )
            continue

        original_hkd = pos["hkd_amount"]
        revalued_hkd = round(pos["foreign_amount"] * closing, 2)

        if pos["transaction_type"] == "receivable":
            unrealized = round(revalued_hkd - original_hkd, 2)
        else:
            unrealized = round(original_hkd - revalued_hkd, 2)

        result = {
            "tx_id": pos["id"],
            "client_id": pos.get("client_id"),
            "currency": currency,
            "outstanding_foreign_amount": pos["foreign_amount"],
            "original_hkd_amount": original_hkd,
            "closing_rate": closing,
            "revalued_hkd_amount": revalued_hkd,
            "unrealized_gain_loss": unrealized,
            "direction": "gain" if unrealized >= 0 else "loss",
        }
        results.append(result)

    _persist_revaluations(period_end_date, results, db_path)

    total = sum(r["unrealized_gain_loss"] for r in results)
    logger.info(
        "Unrealized G/L at %s: %d positions, total HKD %.2f",
        period_end_date, len(results), total,
    )

    return results


def _persist_revaluations(
    period_end_date: date,
    results: list[dict[str, Any]],
    db_path: str | Path,
) -> None:
    """Store revaluation records for audit purposes."""
    with get_db(db_path) as conn:
        for r in results:
            conn.execute(
                """INSERT INTO revaluations
                   (client_id, period_end_date, currency, outstanding_foreign_amount,
                    original_hkd_amount, closing_rate, revalued_hkd_amount,
                    unrealized_gain_loss)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    r.get("client_id"),
                    period_end_date.isoformat(),
                    r["currency"],
                    r["outstanding_foreign_amount"],
                    r["original_hkd_amount"],
                    r["closing_rate"],
                    r["revalued_hkd_amount"],
                    r["unrealized_gain_loss"],
                ),
            )


def summarize_unrealized_by_currency(
    period_end_date: str | date,
    db_path: str | Path,
) -> list[dict[str, Any]]:
    """Aggregate unrealized G/L by currency for a specific period-end."""
    if isinstance(period_end_date, date):
        period_end_date = period_end_date.isoformat()

    with get_db(db_path) as conn:
        rows = conn.execute(
            """SELECT
                currency,
                COUNT(*) as position_count,
                SUM(outstanding_foreign_amount) as total_foreign,
                SUM(original_hkd_amount) as total_original_hkd,
                SUM(revalued_hkd_amount) as total_revalued_hkd,
                SUM(unrealized_gain_loss) as total_unrealized
               FROM revaluations
               WHERE period_end_date = ?
               GROUP BY currency
               ORDER BY currency""",
            (period_end_date,),
        ).fetchall()

    return [
        {
            "currency": r["currency"],
            "position_count": r["position_count"],
            "total_foreign": r["total_foreign"],
            "total_original_hkd": round(r["total_original_hkd"], 2),
            "total_revalued_hkd": round(r["total_revalued_hkd"], 2),
            "total_unrealized": round(r["total_unrealized"], 2),
        }
        for r in rows
    ]
