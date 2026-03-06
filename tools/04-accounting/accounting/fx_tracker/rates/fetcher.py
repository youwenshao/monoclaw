"""Multi-source exchange rate fetcher with retry logic."""

from __future__ import annotations

import asyncio
import logging
from datetime import date
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("openclaw.accounting.fx.fetcher")

USD_HKD_LOWER = 7.75
USD_HKD_UPPER = 7.85


@dataclass
class RateRecord:
    date: date
    base_currency: str
    target_currency: str
    buying_tt: float | None
    selling_tt: float | None
    mid_rate: float
    source: str
    is_interpolated: bool = False


@dataclass
class FetchConfig:
    max_retries: int = 3
    retry_delay_seconds: float = 2.0
    sources: list[str] = field(default_factory=lambda: ["hkma"])


async def fetch_rates(
    target_date: date,
    currencies: list[str] | None = None,
    config: FetchConfig | None = None,
) -> list[RateRecord]:
    """Fetch exchange rates for the target date from configured sources.

    Tries HKMA first, with retries on failure. Validates USD/HKD within
    the 7.75–7.85 linked exchange rate band.
    """
    cfg = config or FetchConfig()
    records: list[RateRecord] = []

    for attempt in range(1, cfg.max_retries + 1):
        try:
            records = await _fetch_from_hkma(target_date)
            if records:
                break
        except Exception as exc:
            logger.warning(
                "HKMA fetch attempt %d/%d failed: %s",
                attempt, cfg.max_retries, exc,
            )
            if attempt < cfg.max_retries:
                await asyncio.sleep(cfg.retry_delay_seconds * attempt)

    if not records:
        logger.error("All rate fetch attempts exhausted for %s", target_date)
        return []

    if currencies:
        upper_currencies = {c.upper() for c in currencies}
        records = [r for r in records if r.target_currency in upper_currencies]

    validated = []
    for record in records:
        if record.target_currency == "USD":
            if not _validate_usd_hkd(record.mid_rate):
                logger.warning(
                    "USD/HKD rate %.4f outside band [%.2f–%.2f] on %s — flagging",
                    record.mid_rate, USD_HKD_LOWER, USD_HKD_UPPER, target_date,
                )
        validated.append(record)

    return validated


async def _fetch_from_hkma(target_date: date) -> list[RateRecord]:
    from accounting.fx_tracker.rates.hkma import fetch_daily_rates

    raw_rates = await fetch_daily_rates(target_date)
    return [
        RateRecord(
            date=date.fromisoformat(r["date"]) if isinstance(r["date"], str) else r["date"],
            base_currency=r["base_currency"],
            target_currency=r["target_currency"],
            buying_tt=r.get("buying_tt"),
            selling_tt=r.get("selling_tt"),
            mid_rate=r["mid_rate"],
            source=r.get("source", "HKMA"),
        )
        for r in raw_rates
    ]


def _validate_usd_hkd(rate: float) -> bool:
    """Check that USD/HKD sits within the linked exchange rate band."""
    return USD_HKD_LOWER <= rate <= USD_HKD_UPPER


def rate_records_to_dicts(records: list[RateRecord]) -> list[dict[str, Any]]:
    """Convert RateRecord list to list of dicts for DB insertion."""
    return [
        {
            "date": r.date.isoformat(),
            "base_currency": r.base_currency,
            "target_currency": r.target_currency,
            "buying_tt": r.buying_tt,
            "selling_tt": r.selling_tt,
            "mid_rate": r.mid_rate,
            "source": r.source,
        }
        for r in records
    ]
