"""Period-end FX revaluation for unsettled positions."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from openclaw_shared.database import get_db

logger = logging.getLogger("openclaw.accounting.fx.revaluation")


@dataclass
class RevaluationResult:
    tx_id: int
    currency: str
    outstanding_foreign_amount: float
    original_hkd_amount: float
    closing_rate: float
    revalued_hkd_amount: float
    unrealized_gain_loss: float


def revalue_positions(
    period_end_date: date | str,
    db_path: str | Path,
) -> list[RevaluationResult]:
    """Revalue all unsettled FX positions at closing rates.

    For each unsettled transaction, fetches the closing rate at period end
    and calculates unrealized gain/loss. Results are stored in the
    revaluations table for audit trail.
    """
    if isinstance(period_end_date, str):
        period_end_date = date.fromisoformat(period_end_date)

    from accounting.fx_tracker.rates.cache import get_closing_rate
    from accounting.fx_tracker.transactions.logger import get_open_positions

    positions = get_open_positions(db_path)

    if not positions:
        logger.info("No open positions to revalue at %s", period_end_date)
        return []

    results: list[RevaluationResult] = []

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
            unrealized = revalued_hkd - original_hkd
        else:
            unrealized = original_hkd - revalued_hkd

        unrealized = round(unrealized, 2)

        result = RevaluationResult(
            tx_id=pos["id"],
            currency=currency,
            outstanding_foreign_amount=pos["foreign_amount"],
            original_hkd_amount=original_hkd,
            closing_rate=closing,
            revalued_hkd_amount=revalued_hkd,
            unrealized_gain_loss=unrealized,
        )
        results.append(result)

    _store_revaluations(period_end_date, results, db_path)

    total = sum(r.unrealized_gain_loss for r in results)
    logger.info(
        "Revalued %d positions at %s. Total unrealized G/L: HKD %.2f",
        len(results), period_end_date, total,
    )

    return results


def _store_revaluations(
    period_end_date: date,
    results: list[RevaluationResult],
    db_path: str | Path,
) -> None:
    """Persist revaluation results for audit trail."""
    with get_db(db_path) as conn:
        for r in results:
            conn.execute(
                """INSERT INTO revaluations
                   (period_end_date, currency, outstanding_foreign_amount,
                    original_hkd_amount, closing_rate, revalued_hkd_amount,
                    unrealized_gain_loss)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    period_end_date.isoformat(),
                    r.currency,
                    r.outstanding_foreign_amount,
                    r.original_hkd_amount,
                    r.closing_rate,
                    r.revalued_hkd_amount,
                    r.unrealized_gain_loss,
                ),
            )


def get_revaluation_history(
    db_path: str | Path,
    period_end_date: str | None = None,
) -> list[dict[str, Any]]:
    """Retrieve revaluation records, optionally filtered by period."""
    with get_db(db_path) as conn:
        if period_end_date:
            rows = conn.execute(
                "SELECT * FROM revaluations WHERE period_end_date = ? ORDER BY currency",
                (period_end_date,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM revaluations ORDER BY period_end_date DESC, currency"
            ).fetchall()
    return [dict(r) for r in rows]
