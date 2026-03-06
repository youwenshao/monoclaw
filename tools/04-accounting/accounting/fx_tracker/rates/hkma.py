"""HKMA Exchange Rate API client."""

from __future__ import annotations

import httpx
import logging
from datetime import date
from typing import Any

logger = logging.getLogger("openclaw.accounting.fx.hkma")

HKMA_API_BASE = (
    "https://api.hkma.gov.hk/public/market-data-and-statistics/"
    "daily-monetary-statistics/daily-figures-interbank-liquidity"
)

HKMA_EXCHANGE_RATE_URL = (
    "https://api.hkma.gov.hk/public/market-data-and-statistics/"
    "monthly-statistical-bulletin/er-ir/er-eeri-daily"
)

DEFAULT_TIMEOUT = 10.0


async def fetch_daily_rates(target_date: date | None = None) -> list[dict[str, Any]]:
    """Fetch exchange rates from HKMA for the given date.

    Uses the HKMA Open API for daily exchange rate data. Returns a list of
    standardized rate records with base_currency=HKD.
    """
    params: dict[str, str] = {"pagesize": "100"}
    if target_date:
        date_str = target_date.strftime("%Y-%m-%d")
        params["choose"] = "EXR"
        params["from"] = date_str
        params["to"] = date_str

    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
            resp = await client.get(HKMA_EXCHANGE_RATE_URL, params=params)
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPStatusError as exc:
        logger.error("HKMA API HTTP error %s: %s", exc.response.status_code, exc)
        return []
    except httpx.RequestError as exc:
        logger.error("HKMA API request failed: %s", exc)
        return []

    return parse_hkma_response(data, target_date)


def parse_hkma_response(data: dict, target_date: date | None = None) -> list[dict[str, Any]]:
    """Parse HKMA API response into standardized rate records.

    Each record: {date, base_currency, target_currency, buying_tt, selling_tt, mid_rate, source}
    """
    records: list[dict[str, Any]] = []

    body = data.get("result", data) if isinstance(data, dict) else {}
    entries = body.get("records", [])

    for entry in entries:
        try:
            rate_date = entry.get("end_of_date") or entry.get("yearmonth")
            if rate_date and len(rate_date) == 10:
                rate_date_obj = date.fromisoformat(rate_date)
            elif target_date:
                rate_date_obj = target_date
            else:
                rate_date_obj = date.today()

            usd_rate = _safe_float(entry.get("er_usd"))
            if usd_rate:
                records.append(_build_record(rate_date_obj, "USD", usd_rate))

            for ccy_key, ccy_code in _CURRENCY_MAP.items():
                rate_val = _safe_float(entry.get(ccy_key))
                if rate_val:
                    records.append(_build_record(rate_date_obj, ccy_code, rate_val))

        except (ValueError, KeyError) as exc:
            logger.warning("Skipping malformed HKMA entry: %s", exc)
            continue

    return records


_CURRENCY_MAP = {
    "er_euro": "EUR",
    "er_jpy": "JPY",
    "er_gbp": "GBP",
    "er_rmb": "CNH",
    "er_aud": "AUD",
    "er_cad": "CAD",
    "er_sgd": "SGD",
    "er_chf": "CHF",
    "er_nzd": "NZD",
}


def _build_record(rate_date: date, currency: str, mid_rate: float) -> dict[str, Any]:
    spread = mid_rate * 0.001
    return {
        "date": rate_date.isoformat(),
        "base_currency": "HKD",
        "target_currency": currency,
        "buying_tt": round(mid_rate - spread, 6),
        "selling_tt": round(mid_rate + spread, 6),
        "mid_rate": round(mid_rate, 6),
        "source": "HKMA",
    }


def _safe_float(val: Any) -> float | None:
    if val is None:
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None
