"""Currency conversion utilities with HKD peg band monitoring."""

from __future__ import annotations

from import_export.fx_invoice.fx.rate_cache import RateCache

HKD_PEG_LOWER = 7.75
HKD_PEG_UPPER = 7.85
HKD_PEG_WARN_BUFFER = 0.02


class CurrencyConverter:

    def __init__(self, rate_cache: RateCache) -> None:
        self.rate_cache = rate_cache

    def convert(
        self,
        amount: float,
        from_currency: str,
        to_currency: str,
        rate: float | None = None,
    ) -> dict:
        """Convert an amount between currencies.

        Returns {"amount": float, "rate": float, "result": float}.
        """
        if from_currency == to_currency:
            return {"amount": amount, "rate": 1.0, "result": amount}

        if rate is None:
            cached = self.rate_cache.get_latest_rate(from_currency, to_currency)
            if cached:
                rate = cached["rate"]
            else:
                reverse = self.rate_cache.get_latest_rate(to_currency, from_currency)
                if reverse and reverse["rate"]:
                    rate = 1.0 / reverse["rate"]
                else:
                    raise ValueError(
                        f"No rate available for {from_currency}/{to_currency}"
                    )

        result = round(amount * rate, 2)
        return {"amount": amount, "rate": rate, "result": result}

    def to_hkd(self, amount: float, currency: str) -> float:
        """Convert an arbitrary currency amount to HKD."""
        if currency == "HKD":
            return amount
        conversion = self.convert(amount, currency, "HKD")
        return conversion["result"]

    def check_peg_band(self, usd_hkd_rate: float) -> dict:
        """Check if the USD/HKD rate is near the peg band edges (7.75–7.85)."""
        within_band = HKD_PEG_LOWER <= usd_hkd_rate <= HKD_PEG_UPPER
        near_strong = usd_hkd_rate <= HKD_PEG_LOWER + HKD_PEG_WARN_BUFFER
        near_weak = usd_hkd_rate >= HKD_PEG_UPPER - HKD_PEG_WARN_BUFFER

        if near_strong:
            warning = "Rate near strong-side convertibility undertaking (7.75)"
        elif near_weak:
            warning = "Rate near weak-side convertibility undertaking (7.85)"
        else:
            warning = None

        return {
            "rate": usd_hkd_rate,
            "within_band": within_band,
            "near_strong_side": near_strong,
            "near_weak_side": near_weak,
            "peg_lower": HKD_PEG_LOWER,
            "peg_upper": HKD_PEG_UPPER,
            "warning": warning,
        }
