"""Multi-currency matching with exchange rate tolerance.

When bank transactions and ledger entries are in different currencies,
apply an FX rate window to determine whether amounts match after conversion.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

from .strategies import MatchConfig


@dataclass
class FXRate:
    from_currency: str
    to_currency: str
    rate: float
    rate_date: date


def _get_rate(
    rates: list[FXRate],
    from_ccy: str,
    to_ccy: str,
    target_date: date,
    tolerance_days: int = 5,
) -> float | None:
    """Find the closest available rate within the tolerance window."""
    candidates = [
        r for r in rates
        if r.from_currency == from_ccy
        and r.to_currency == to_ccy
        and abs((r.rate_date - target_date).days) <= tolerance_days
    ]
    if not candidates:
        inverse = [
            r for r in rates
            if r.from_currency == to_ccy
            and r.to_currency == from_ccy
            and abs((r.rate_date - target_date).days) <= tolerance_days
        ]
        if inverse:
            closest = min(inverse, key=lambda r: abs((r.rate_date - target_date).days))
            return 1.0 / closest.rate if closest.rate != 0 else None
        return None

    closest = min(candidates, key=lambda r: abs((r.rate_date - target_date).days))
    return closest.rate


def fx_amount_match(
    bank_amount: float,
    bank_currency: str,
    ledger_amount: float,
    ledger_currency: str,
    rates: list[FXRate],
    reference_date: date,
    config: MatchConfig,
) -> tuple[bool, float]:
    """Check if two amounts in different currencies match within FX tolerance.

    Returns (is_match, confidence).
    """
    if bank_currency == ledger_currency:
        diff = abs(bank_amount - ledger_amount)
        return diff <= config.amount_tolerance, 0.95 if diff <= config.amount_tolerance else 0.0

    rate = _get_rate(rates, bank_currency, ledger_currency, reference_date)
    if rate is None:
        return False, 0.0

    converted = bank_amount * rate
    diff_pct = abs(converted - ledger_amount) / max(ledger_amount, 0.01) * 100

    is_match = diff_pct <= config.fx_rate_tolerance_pct
    confidence = max(0.0, 0.90 - diff_pct * 0.1) if is_match else 0.0

    return is_match, round(confidence, 2)


def fx_cross_currency_match(
    bank_txns: list[dict[str, Any]],
    ledger_entries: list[dict[str, Any]],
    rates: list[FXRate],
    config: MatchConfig,
) -> list[tuple[int, int, float, str]]:
    """Match bank transactions and ledger entries across different currencies.

    Only considers pairs where currencies differ.
    """
    matches: list[tuple[int, int, float, str]] = []
    used_bank: set[int] = set()
    used_ledger: set[int] = set()

    for b in bank_txns:
        if b["id"] in used_bank:
            continue
        b_ccy = (b.get("currency") or "HKD").upper()
        b_amount = max(float(b.get("debit", 0) or 0), float(b.get("credit", 0) or 0))
        b_date_raw = b.get("transaction_date")
        b_date = date.fromisoformat(b_date_raw) if isinstance(b_date_raw, str) else b_date_raw
        if not isinstance(b_date, date) or b_amount == 0:
            continue

        for le in ledger_entries:
            if le["id"] in used_ledger:
                continue
            le_ccy = (le.get("currency") or "HKD").upper()
            if le_ccy == b_ccy:
                continue

            le_amount = max(float(le.get("debit", 0) or 0), float(le.get("credit", 0) or 0))
            if le_amount == 0:
                continue

            is_match, confidence = fx_amount_match(
                b_amount, b_ccy, le_amount, le_ccy, rates, b_date, config,
            )
            if is_match and confidence > 0.5:
                matches.append((b["id"], le["id"], confidence, "fx_cross_currency"))
                used_bank.add(b["id"])
                used_ledger.add(le["id"])
                break

    return matches
