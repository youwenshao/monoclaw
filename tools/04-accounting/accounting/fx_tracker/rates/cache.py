"""Exchange rate caching and interpolation."""

from __future__ import annotations

import logging
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from openclaw_shared.database import get_db

logger = logging.getLogger("openclaw.accounting.fx.cache")


def get_rate(
    target_date: date,
    currency: str,
    db_path: str | Path,
) -> float | None:
    """Get mid-rate for a currency on a given date.

    Lookup order:
    1. Exact date match in DB cache
    2. Linear interpolation between nearest bracketing dates
    3. None if no data available
    """
    currency = currency.upper()

    exact = _lookup_exact(target_date, currency, db_path)
    if exact is not None:
        return exact

    interpolated = _interpolate(target_date, currency, db_path)
    if interpolated is not None:
        _store_rate(target_date, currency, interpolated, db_path, source="interpolated")
        logger.info(
            "Interpolated %s rate for %s: %.6f",
            currency, target_date, interpolated,
        )
        return interpolated

    return None


def store_rates(rates: list[dict[str, Any]], db_path: str | Path) -> int:
    """Bulk-store rate records into the exchange_rates table. Returns insert count."""
    count = 0
    with get_db(db_path) as conn:
        for r in rates:
            try:
                conn.execute(
                    """INSERT OR IGNORE INTO exchange_rates
                       (date, base_currency, target_currency, buying_tt, selling_tt, mid_rate, source)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (
                        r["date"],
                        r.get("base_currency", "HKD"),
                        r["target_currency"],
                        r.get("buying_tt"),
                        r.get("selling_tt"),
                        r["mid_rate"],
                        r.get("source", "HKMA"),
                    ),
                )
                count += 1
            except Exception as exc:
                logger.warning("Failed to store rate %s: %s", r, exc)
    return count


def get_latest_rate(currency: str, db_path: str | Path) -> float | None:
    """Return the most recent mid-rate for a given currency."""
    currency = currency.upper()
    with get_db(db_path) as conn:
        row = conn.execute(
            """SELECT mid_rate FROM exchange_rates
               WHERE target_currency = ?
               ORDER BY date DESC LIMIT 1""",
            (currency,),
        ).fetchone()
    return row["mid_rate"] if row else None


def get_closing_rate(period_end: date, currency: str, db_path: str | Path) -> float | None:
    """Get the closing rate for period-end revaluation.

    Tries exact date first, then falls back to the most recent rate before
    the period end (within 5 business days).
    """
    currency = currency.upper()
    exact = _lookup_exact(period_end, currency, db_path)
    if exact is not None:
        return exact

    with get_db(db_path) as conn:
        row = conn.execute(
            """SELECT mid_rate FROM exchange_rates
               WHERE target_currency = ? AND date <= ? AND date >= ?
               ORDER BY date DESC LIMIT 1""",
            (currency, period_end.isoformat(), (period_end - timedelta(days=7)).isoformat()),
        ).fetchone()

    return row["mid_rate"] if row else None


def _lookup_exact(target_date: date, currency: str, db_path: str | Path) -> float | None:
    with get_db(db_path) as conn:
        row = conn.execute(
            """SELECT mid_rate FROM exchange_rates
               WHERE date = ? AND target_currency = ?
               LIMIT 1""",
            (target_date.isoformat(), currency),
        ).fetchone()
    return row["mid_rate"] if row else None


def _interpolate(target_date: date, currency: str, db_path: str | Path) -> float | None:
    """Linearly interpolate between the closest rates before and after target_date."""
    with get_db(db_path) as conn:
        before = conn.execute(
            """SELECT date, mid_rate FROM exchange_rates
               WHERE target_currency = ? AND date < ?
               ORDER BY date DESC LIMIT 1""",
            (currency, target_date.isoformat()),
        ).fetchone()

        after = conn.execute(
            """SELECT date, mid_rate FROM exchange_rates
               WHERE target_currency = ? AND date > ?
               ORDER BY date ASC LIMIT 1""",
            (currency, target_date.isoformat()),
        ).fetchone()

    if before and after:
        d0 = date.fromisoformat(before["date"])
        d1 = date.fromisoformat(after["date"])
        r0 = before["mid_rate"]
        r1 = after["mid_rate"]

        total_days = (d1 - d0).days
        if total_days == 0:
            return r0

        elapsed = (target_date - d0).days
        ratio = elapsed / total_days
        return round(r0 + (r1 - r0) * ratio, 6)

    if before:
        return before["mid_rate"]

    return None


def _store_rate(
    target_date: date,
    currency: str,
    rate: float,
    db_path: str | Path,
    source: str = "interpolated",
) -> None:
    with get_db(db_path) as conn:
        conn.execute(
            """INSERT OR IGNORE INTO exchange_rates
               (date, base_currency, target_currency, mid_rate, source)
               VALUES (?, 'HKD', ?, ?, ?)""",
            (target_date.isoformat(), currency, rate, source),
        )
