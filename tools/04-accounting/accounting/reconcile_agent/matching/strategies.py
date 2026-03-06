"""Individual matching strategies for bank-to-ledger reconciliation.

Each strategy function takes lists of unmatched bank and ledger entries and
returns a list of (bank_id, ledger_id, confidence, strategy_name) tuples.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

from rapidfuzz import fuzz

Match = tuple[int, int, float, str]


@dataclass
class MatchConfig:
    date_tolerance_days: int = 3
    amount_tolerance: float = 1.0
    fuzzy_threshold: int = 80
    fx_rate_tolerance_pct: float = 1.0


def _net_amount(entry: dict[str, Any]) -> float:
    """Return signed net: positive for credits/deposits, negative for debits."""
    debit = float(entry.get("debit", 0) or 0)
    credit = float(entry.get("credit", 0) or 0)
    if credit > 0:
        return credit
    if debit > 0:
        return -debit
    return 0.0


def _abs_amount(entry: dict[str, Any]) -> float:
    debit = float(entry.get("debit", 0) or 0)
    credit = float(entry.get("credit", 0) or 0)
    return max(debit, credit)


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


def _amounts_close(a: float, b: float, tolerance: float) -> bool:
    return abs(a - b) <= tolerance


def _dates_close(d1: date | None, d2: date | None, days: int) -> bool:
    if d1 is None or d2 is None:
        return False
    return abs((d1 - d2).days) <= days


def _payee_text(entry: dict[str, Any]) -> str:
    return (entry.get("description") or "").strip().upper()


# ─── Strategy: Exact reference + amount ────────────────────────────────

def reference_match(
    bank_txns: list[dict],
    ledger_entries: list[dict],
    config: MatchConfig,
) -> list[Match]:
    """Match on exact reference string + amount within tolerance."""
    matches: list[Match] = []
    used_ledger: set[int] = set()

    bank_by_ref: dict[str, list[dict]] = {}
    for b in bank_txns:
        ref = (b.get("reference") or "").strip().upper()
        if ref:
            bank_by_ref.setdefault(ref, []).append(b)

    for le in ledger_entries:
        le_ref = (le.get("reference") or "").strip().upper()
        if not le_ref or le["id"] in used_ledger:
            continue

        candidates = bank_by_ref.get(le_ref, [])
        le_amount = _abs_amount(le)

        for b in candidates:
            if _amounts_close(_abs_amount(b), le_amount, config.amount_tolerance):
                matches.append((b["id"], le["id"], 0.99, "reference"))
                used_ledger.add(le["id"])
                break

    return matches


# ─── Strategy: Exact amount + date proximity ───────────────────────────

def exact_amount_match(
    bank_txns: list[dict],
    ledger_entries: list[dict],
    config: MatchConfig,
) -> list[Match]:
    matches: list[Match] = []
    used_bank: set[int] = set()
    used_ledger: set[int] = set()

    for b in bank_txns:
        if b["id"] in used_bank:
            continue
        b_amount = _abs_amount(b)
        b_date = _entry_date(b)
        b_is_debit = float(b.get("debit", 0) or 0) > 0

        best: tuple[int, int] | None = None
        best_days = config.date_tolerance_days + 1

        for le in ledger_entries:
            if le["id"] in used_ledger:
                continue
            le_amount = _abs_amount(le)
            le_date = _entry_date(le)
            le_is_debit = float(le.get("debit", 0) or 0) > 0

            if not _amounts_close(b_amount, le_amount, config.amount_tolerance):
                continue
            if b_is_debit != le_is_debit:
                continue
            if not _dates_close(b_date, le_date, config.date_tolerance_days):
                continue

            day_diff = abs((b_date - le_date).days) if b_date and le_date else config.date_tolerance_days
            if day_diff < best_days:
                best_days = day_diff
                best = (b["id"], le["id"])

        if best:
            confidence = max(0.80, 0.95 - best_days * 0.03)
            matches.append((best[0], best[1], confidence, "exact_amount"))
            used_bank.add(best[0])
            used_ledger.add(best[1])

    return matches


# ─── Strategy: Date proximity ──────────────────────────────────────────

def date_proximity_match(
    bank_txns: list[dict],
    ledger_entries: list[dict],
    config: MatchConfig,
) -> list[Match]:
    """Looser date-only proximity for similar amounts (within 5%)."""
    matches: list[Match] = []
    used_bank: set[int] = set()
    used_ledger: set[int] = set()

    for b in bank_txns:
        if b["id"] in used_bank:
            continue
        b_amount = _abs_amount(b)
        b_date = _entry_date(b)
        if b_amount == 0:
            continue

        best: tuple[int, int] | None = None
        best_score = 0.0

        for le in ledger_entries:
            if le["id"] in used_ledger:
                continue
            le_amount = _abs_amount(le)
            le_date = _entry_date(le)

            if le_amount == 0:
                continue
            amount_diff_pct = abs(b_amount - le_amount) / max(b_amount, le_amount) * 100
            if amount_diff_pct > 5.0:
                continue
            if not _dates_close(b_date, le_date, config.date_tolerance_days + 2):
                continue

            day_diff = abs((b_date - le_date).days) if b_date and le_date else 5
            score = (100 - amount_diff_pct) * 0.6 + (10 - min(day_diff, 10)) * 4.0
            if score > best_score:
                best_score = score
                best = (b["id"], le["id"])

        if best and best_score > 60:
            matches.append((best[0], best[1], round(best_score / 130, 2), "date_proximity"))
            used_bank.add(best[0])
            used_ledger.add(best[1])

    return matches


# ─── Strategy: Fuzzy payee name ────────────────────────────────────────

def fuzzy_payee_match(
    bank_txns: list[dict],
    ledger_entries: list[dict],
    config: MatchConfig,
) -> list[Match]:
    """Match on fuzzy description similarity + approximate amount."""
    matches: list[Match] = []
    used_bank: set[int] = set()
    used_ledger: set[int] = set()

    for b in bank_txns:
        if b["id"] in used_bank:
            continue
        b_text = _payee_text(b)
        b_amount = _abs_amount(b)
        if not b_text or b_amount == 0:
            continue

        best: tuple[int, int] | None = None
        best_score = 0.0

        for le in ledger_entries:
            if le["id"] in used_ledger:
                continue
            le_text = _payee_text(le)
            le_amount = _abs_amount(le)
            if not le_text or le_amount == 0:
                continue

            amount_diff_pct = abs(b_amount - le_amount) / max(b_amount, le_amount) * 100
            if amount_diff_pct > 10.0:
                continue

            text_score = fuzz.token_sort_ratio(b_text, le_text)
            if text_score < config.fuzzy_threshold:
                continue

            combined = text_score * 0.6 + (100 - amount_diff_pct) * 0.4
            if combined > best_score:
                best_score = combined
                best = (b["id"], le["id"])

        if best and best_score > 65:
            matches.append((best[0], best[1], round(min(best_score / 100, 0.90), 2), "fuzzy_payee"))
            used_bank.add(best[0])
            used_ledger.add(best[1])

    return matches


# ─── Strategy: Aggregate (many-to-one) matching ────────────────────────

def aggregate_match(
    bank_txns: list[dict],
    ledger_entries: list[dict],
    config: MatchConfig,
    max_combination_size: int = 4,
) -> list[tuple[list[int], int, float, str]]:
    """Try combinations of 2-4 bank transactions that sum to a ledger amount.

    Returns list of (bank_ids_list, ledger_id, confidence, strategy_name).
    """
    from itertools import combinations

    results: list[tuple[list[int], int, float, str]] = []
    used_ledger: set[int] = set()

    ledger_sorted = sorted(ledger_entries, key=lambda e: _abs_amount(e), reverse=True)

    bank_items = [(b["id"], _abs_amount(b), _entry_date(b)) for b in bank_txns if _abs_amount(b) > 0]

    for le in ledger_sorted:
        if le["id"] in used_ledger:
            continue
        target = _abs_amount(le)
        if target == 0:
            continue
        le_date = _entry_date(le)

        for size in range(2, max_combination_size + 1):
            found = False
            for combo in combinations(bank_items, size):
                combo_sum = sum(amt for _, amt, _ in combo)
                if not _amounts_close(combo_sum, target, config.amount_tolerance):
                    continue

                if le_date:
                    combo_dates = [d for _, _, d in combo if d is not None]
                    if combo_dates and all(
                        abs((d - le_date).days) <= config.date_tolerance_days + 3
                        for d in combo_dates
                    ):
                        bank_ids = [bid for bid, _, _ in combo]
                        confidence = max(0.60, 0.85 - size * 0.05)
                        results.append((bank_ids, le["id"], confidence, "aggregate"))
                        used_ledger.add(le["id"])
                        found = True
                        break

            if found:
                break

    return results
