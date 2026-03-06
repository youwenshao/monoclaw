"""Live FX rate fetching with configurable sources and fallback mock data."""

from __future__ import annotations

import logging

import httpx

logger = logging.getLogger("openclaw.import-export.fx")

MOCK_RATES_HKD: dict[str, float] = {
    "USD": 0.1282,
    "CNH": 0.9310,
    "CNY": 0.9310,
    "EUR": 0.1180,
    "GBP": 0.1015,
    "JPY": 19.45,
    "SGD": 0.1715,
    "AUD": 0.1980,
    "CAD": 0.1750,
    "CHF": 0.1135,
    "KRW": 172.0,
    "TWD": 4.15,
    "THB": 4.57,
    "MYR": 0.6030,
    "INR": 10.72,
    "VND": 3230.0,
}

DEFAULT_TARGETS = ["USD", "CNH", "EUR", "GBP", "JPY", "SGD"]


class RateFetcher:

    def __init__(self, source: str = "exchangerate-api") -> None:
        self.source = source

    def fetch_rates(
        self, base: str = "HKD", targets: list[str] | None = None
    ) -> dict:
        """Fetch live rates via httpx; falls back to mock data on failure."""
        targets = targets or DEFAULT_TARGETS

        try:
            if self.source == "hkma":
                return self._fetch_from_hkma()
            return self._fetch_from_exchangerate_api(base, targets)
        except Exception as exc:
            logger.warning("Live FX fetch failed (%s), using mock rates: %s", self.source, exc)
            return self._mock_rates(base, targets)

    def fetch_single_rate(self, base: str, target: str) -> float:
        """Fetch a single conversion rate."""
        rates = self.fetch_rates(base, [target])
        rate = rates.get("rates", {}).get(target)
        if rate is None:
            raise ValueError(f"Rate not available for {base}/{target}")
        return rate

    def _fetch_from_exchangerate_api(
        self, base: str, targets: list[str]
    ) -> dict:
        """Fetch from exchangerate-api.com (free tier)."""
        url = f"https://open.er-api.com/v6/latest/{base}"
        with httpx.Client(timeout=10) as client:
            resp = client.get(url)
            resp.raise_for_status()
            data = resp.json()

        if data.get("result") != "success":
            raise RuntimeError(f"API returned non-success: {data.get('result')}")

        all_rates = data.get("rates", {})
        filtered = {t: all_rates[t] for t in targets if t in all_rates}

        return {
            "base": base,
            "rates": filtered,
            "source": "exchangerate-api",
            "timestamp": data.get("time_last_update_utc", ""),
        }

    def _fetch_from_hkma(self) -> dict:
        """Fetch USD/HKD from the HKMA API."""
        url = "https://api.hkma.gov.hk/public/market-data-and-statistics/monthly-statistical-bulletin/er-ir/er-eeri-end-of-month"
        with httpx.Client(timeout=10) as client:
            resp = client.get(url)
            resp.raise_for_status()
            data = resp.json()

        records = data.get("result", {}).get("records", [])
        rates: dict[str, float] = {}
        if records:
            latest = records[0]
            usd_hkd = latest.get("er_usd_hkd")
            if usd_hkd:
                rates["USD"] = float(usd_hkd)

        return {
            "base": "HKD",
            "rates": rates,
            "source": "hkma",
            "timestamp": records[0].get("end_of_month", "") if records else "",
        }

    @staticmethod
    def _mock_rates(base: str, targets: list[str]) -> dict:
        """Return hard-coded fallback rates for development/offline use."""
        if base == "HKD":
            rates = {t: MOCK_RATES_HKD[t] for t in targets if t in MOCK_RATES_HKD}
        else:
            base_to_hkd = 1.0 / MOCK_RATES_HKD.get(base, 1.0)
            rates = {}
            for t in targets:
                if t == "HKD":
                    rates[t] = base_to_hkd
                elif t in MOCK_RATES_HKD:
                    rates[t] = MOCK_RATES_HKD[t] * base_to_hkd

        return {"base": base, "rates": rates, "source": "mock", "timestamp": ""}
