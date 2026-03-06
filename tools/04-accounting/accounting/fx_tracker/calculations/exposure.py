"""Net FX exposure calculator."""

from __future__ import annotations

import logging
from datetime import date
from pathlib import Path
from typing import Any

from openclaw_shared.database import get_db

logger = logging.getLogger("openclaw.accounting.fx.exposure")


def calculate_exposure(db_path: str | Path) -> list[dict[str, Any]]:
    """Calculate net currency exposure from unsettled FX transactions.

    Groups open positions by currency and computes:
    - Receivables (inflows) in foreign and HKD
    - Payables (outflows) in foreign and HKD
    - Net exposure in both foreign and HKD terms

    Results are stored in the fx_exposure table for historical tracking.
    """
    with get_db(db_path) as conn:
        rows = conn.execute(
            """SELECT
                currency,
                transaction_type,
                SUM(foreign_amount) as total_foreign,
                SUM(hkd_amount) as total_hkd
               FROM fx_transactions
               WHERE is_settled = 0
               GROUP BY currency, transaction_type
               ORDER BY currency"""
        ).fetchall()

    currency_data: dict[str, dict[str, float]] = {}
    for row in rows:
        ccy = row["currency"]
        if ccy not in currency_data:
            currency_data[ccy] = {
                "receivables_foreign": 0.0,
                "receivables_hkd": 0.0,
                "payables_foreign": 0.0,
                "payables_hkd": 0.0,
            }

        if row["transaction_type"] == "receivable":
            currency_data[ccy]["receivables_foreign"] = row["total_foreign"]
            currency_data[ccy]["receivables_hkd"] = row["total_hkd"]
        else:
            currency_data[ccy]["payables_foreign"] = row["total_foreign"]
            currency_data[ccy]["payables_hkd"] = row["total_hkd"]

    exposures: list[dict[str, Any]] = []
    for ccy, data in sorted(currency_data.items()):
        net_foreign = data["receivables_foreign"] - data["payables_foreign"]
        net_hkd = data["receivables_hkd"] - data["payables_hkd"]

        exposure = {
            "currency": ccy,
            "receivables_foreign": round(data["receivables_foreign"], 2),
            "receivables_hkd": round(data["receivables_hkd"], 2),
            "payables_foreign": round(data["payables_foreign"], 2),
            "payables_hkd": round(data["payables_hkd"], 2),
            "net_exposure_foreign": round(net_foreign, 2),
            "net_exposure_hkd": round(net_hkd, 2),
            "direction": "long" if net_foreign > 0 else "short" if net_foreign < 0 else "flat",
        }
        exposures.append(exposure)

    _store_exposure_snapshot(exposures, db_path)

    return exposures


def _store_exposure_snapshot(
    exposures: list[dict[str, Any]],
    db_path: str | Path,
) -> None:
    """Persist current exposure snapshot for trend analysis."""
    today = date.today().isoformat()

    with get_db(db_path) as conn:
        for exp in exposures:
            conn.execute(
                """INSERT INTO fx_exposure
                   (as_of_date, currency, receivables_foreign, payables_foreign,
                    net_exposure_foreign, net_exposure_hkd)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    today,
                    exp["currency"],
                    exp["receivables_foreign"],
                    exp["payables_foreign"],
                    exp["net_exposure_foreign"],
                    exp["net_exposure_hkd"],
                ),
            )


def get_exposure_history(
    currency: str,
    db_path: str | Path,
    limit: int = 30,
) -> list[dict[str, Any]]:
    """Retrieve historical exposure snapshots for a currency."""
    with get_db(db_path) as conn:
        rows = conn.execute(
            """SELECT * FROM fx_exposure
               WHERE currency = ?
               ORDER BY as_of_date DESC
               LIMIT ?""",
            (currency.upper(), limit),
        ).fetchall()
    return [dict(r) for r in rows]


def get_total_exposure_hkd(db_path: str | Path) -> dict[str, float]:
    """Get the aggregate HKD exposure across all currencies."""
    exposures = calculate_exposure(db_path)

    total_receivables = sum(e["receivables_hkd"] for e in exposures)
    total_payables = sum(e["payables_hkd"] for e in exposures)

    return {
        "total_receivables_hkd": round(total_receivables, 2),
        "total_payables_hkd": round(total_payables, 2),
        "net_exposure_hkd": round(total_receivables - total_payables, 2),
        "currency_count": len(exposures),
    }
