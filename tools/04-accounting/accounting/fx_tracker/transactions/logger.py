"""FX transaction recording."""

from __future__ import annotations

import logging
from datetime import date
from pathlib import Path
from typing import Any

from openclaw_shared.database import get_db

logger = logging.getLogger("openclaw.accounting.fx.transactions")


def log_transaction(
    data: dict[str, Any],
    db_path: str | Path,
) -> int:
    """Record a new FX transaction. Returns the transaction ID.

    Required data keys:
        transaction_date, currency, foreign_amount, transaction_type

    Optional keys:
        description, exchange_rate, nature, reference, client_id

    If exchange_rate is not provided, looks up the cached rate for the
    transaction date and currency.
    """
    currency = data["currency"].upper()
    foreign_amount = float(data["foreign_amount"])
    tx_date = data["transaction_date"]
    tx_type = data["transaction_type"]

    exchange_rate = data.get("exchange_rate")
    if exchange_rate is None:
        from accounting.fx_tracker.rates.cache import get_rate
        parsed_date = date.fromisoformat(tx_date) if isinstance(tx_date, str) else tx_date
        exchange_rate = get_rate(parsed_date, currency, db_path)
        if exchange_rate is None:
            raise ValueError(
                f"No exchange rate available for {currency} on {tx_date}. "
                "Provide exchange_rate explicitly."
            )
    else:
        exchange_rate = float(exchange_rate)

    hkd_amount = round(foreign_amount * exchange_rate, 2)

    with get_db(db_path) as conn:
        cursor = conn.execute(
            """INSERT INTO fx_transactions
               (client_id, transaction_date, description, currency, foreign_amount,
                exchange_rate, hkd_amount, transaction_type, nature, reference)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                data.get("client_id"),
                tx_date if isinstance(tx_date, str) else tx_date.isoformat(),
                data.get("description", ""),
                currency,
                foreign_amount,
                exchange_rate,
                hkd_amount,
                tx_type,
                data.get("nature", "revenue"),
                data.get("reference", ""),
            ),
        )
        tx_id = cursor.lastrowid

    logger.info(
        "Logged FX tx #%d: %s %.2f @ %.4f = HKD %.2f (%s)",
        tx_id, currency, foreign_amount, exchange_rate, hkd_amount, tx_type,
    )

    return tx_id


def get_transaction(tx_id: int, db_path: str | Path) -> dict[str, Any] | None:
    """Fetch a single transaction by ID."""
    with get_db(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM fx_transactions WHERE id = ?", (tx_id,)
        ).fetchone()
    return dict(row) if row else None


def get_open_positions(
    db_path: str | Path,
    currency: str | None = None,
) -> list[dict[str, Any]]:
    """Return all unsettled FX transactions, optionally filtered by currency."""
    clauses = ["is_settled = 0"]
    params: list[Any] = []

    if currency:
        clauses.append("currency = ?")
        params.append(currency.upper())

    where = " AND ".join(clauses)

    with get_db(db_path) as conn:
        rows = conn.execute(
            f"SELECT * FROM fx_transactions WHERE {where} ORDER BY transaction_date",
            params,
        ).fetchall()

    return [dict(r) for r in rows]


def get_positions_by_currency(db_path: str | Path) -> dict[str, list[dict[str, Any]]]:
    """Group open positions by currency for exposure/revaluation purposes."""
    positions = get_open_positions(db_path)
    by_currency: dict[str, list[dict[str, Any]]] = {}
    for pos in positions:
        ccy = pos["currency"]
        by_currency.setdefault(ccy, []).append(pos)
    return by_currency
