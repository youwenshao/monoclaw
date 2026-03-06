"""Simple FX hedging recommendation engine for SME traders."""

from __future__ import annotations

HEDGING_THRESHOLD_USD = 50_000
HEDGING_THRESHOLD_DAYS = 60

VOLATILE_CURRENCIES = {"EUR", "GBP", "JPY", "AUD", "CNH", "CNY"}
PEGGED_CURRENCIES = {"USD"}


class HedgingAdvisor:

    def analyze(
        self, invoice_amount: float, currency: str, payment_terms_days: int
    ) -> dict:
        """Produce a hedging recommendation for an open invoice."""
        should_hedge = self.should_suggest_hedging(
            invoice_amount, currency, payment_terms_days
        )
        recommendation = self.get_recommendation(
            currency, invoice_amount, payment_terms_days
        )

        risk_level = "low"
        if currency in VOLATILE_CURRENCIES and payment_terms_days > HEDGING_THRESHOLD_DAYS:
            risk_level = "high"
        elif currency in VOLATILE_CURRENCIES or payment_terms_days > HEDGING_THRESHOLD_DAYS:
            risk_level = "medium"

        return {
            "currency": currency,
            "amount": invoice_amount,
            "payment_terms_days": payment_terms_days,
            "should_hedge": should_hedge,
            "risk_level": risk_level,
            "recommendation": recommendation,
        }

    def should_suggest_hedging(
        self, amount: float, currency: str, days: int
    ) -> bool:
        """Suggest hedging for amounts >USD 50K equivalent and >60 day terms."""
        if currency in PEGGED_CURRENCIES:
            return False
        return amount >= HEDGING_THRESHOLD_USD and days >= HEDGING_THRESHOLD_DAYS

    def get_recommendation(
        self, currency: str, amount: float, days: int
    ) -> str:
        """Generate a human-readable hedging suggestion."""
        if currency in PEGGED_CURRENCIES:
            return (
                f"{currency} is pegged to HKD within the 7.75–7.85 band. "
                "FX risk is minimal; hedging generally not needed."
            )

        if amount < HEDGING_THRESHOLD_USD:
            return (
                f"Exposure of {amount:,.0f} {currency} is below the "
                f"{HEDGING_THRESHOLD_USD:,.0f} USD threshold. "
                "Consider natural hedging through matching receivables/payables."
            )

        if days < HEDGING_THRESHOLD_DAYS:
            return (
                f"Payment terms of {days} days are relatively short. "
                "Monitor rates and consider a spot transaction closer to settlement."
            )

        instruments = []
        if days <= 90:
            instruments.append("a forward contract")
        else:
            instruments.append("a forward contract or FX option")

        if currency in {"EUR", "GBP", "JPY"}:
            instruments.append(
                "consider a participating forward for partial upside"
            )

        suggestion = (
            f"High FX exposure: {amount:,.0f} {currency} over {days} days. "
            f"Recommended: lock in the rate with {' or '.join(instruments)}. "
            "Consult your bank's treasury desk for indicative pricing."
        )
        return suggestion
