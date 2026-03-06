"""FPS (Faster Payment System) specific matching logic.

FPS transactions in HK often carry minimal reference data — just amount +
date. This module uses tighter date tolerance and amount-only matching
with special handling for FPS-labelled entries.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from .strategies import MatchConfig


def _is_fps(entry: dict[str, Any]) -> bool:
    txn_type = (entry.get("transaction_type") or "").lower()
    desc = (entry.get("description") or "").upper()
    return txn_type == "fps" or "FPS" in desc or "FASTER PAYMENT" in desc or "轉數快" in entry.get("description", "")


def _abs_amount(entry: dict[str, Any]) -> float:
    return max(float(entry.get("debit", 0) or 0), float(entry.get("credit", 0) or 0))


def _entry_date(entry: dict[str, Any]) -> date | None:
    raw = entry.get("transaction_date") or entry.get("entry_date")
    if isinstance(raw, date):
        return raw
    if isinstance(raw, str):
        try:
            return date.fromisoformat(raw)
        except ValueError:
            return None
    return None


def fps_match(
    bank_txns: list[dict[str, Any]],
    ledger_entries: list[dict[str, Any]],
    config: MatchConfig,
) -> list[tuple[int, int, float, str]]:
    """Match FPS bank transactions to ledger entries.

    FPS matching uses:
    - Exact amount (tolerance from config)
    - Tight date window (max 1 day for same-day settlement)
    - Direction agreement (both debits or both credits)
    """
    fps_date_tolerance = min(config.date_tolerance_days, 1)

    fps_bank = [b for b in bank_txns if _is_fps(b)]
    if not fps_bank:
        return []

    matches: list[tuple[int, int, float, str]] = []
    used_bank: set[int] = set()
    used_ledger: set[int] = set()

    for b in fps_bank:
        if b["id"] in used_bank:
            continue
        b_amount = _abs_amount(b)
        b_date = _entry_date(b)
        b_is_debit = float(b.get("debit", 0) or 0) > 0

        if b_amount == 0 or b_date is None:
            continue

        best_match: tuple[int, int] | None = None
        best_days = fps_date_tolerance + 1

        for le in ledger_entries:
            if le["id"] in used_ledger:
                continue
            le_amount = _abs_amount(le)
            le_date = _entry_date(le)
            le_is_debit = float(le.get("debit", 0) or 0) > 0

            if abs(b_amount - le_amount) > config.amount_tolerance:
                continue
            if b_is_debit != le_is_debit:
                continue
            if le_date is None:
                continue

            day_diff = abs((b_date - le_date).days)
            if day_diff > fps_date_tolerance:
                continue

            if day_diff < best_days:
                best_days = day_diff
                best_match = (b["id"], le["id"])

        if best_match:
            confidence = 0.92 if best_days == 0 else 0.85
            matches.append((best_match[0], best_match[1], confidence, "fps"))
            used_bank.add(best_match[0])
            used_ledger.add(best_match[1])

    return matches
