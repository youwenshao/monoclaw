"""Core matching orchestrator for bank-to-ledger reconciliation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .strategies import (
    MatchConfig,
    aggregate_match,
    date_proximity_match,
    exact_amount_match,
    fuzzy_payee_match,
    reference_match,
)


@dataclass
class MatchPair:
    bank_id: int
    ledger_id: int
    confidence: float
    strategy: str


@dataclass
class AggregateMatchPair:
    bank_ids: list[int]
    ledger_id: int
    confidence: float
    strategy: str


@dataclass
class MatchResult:
    matches: list[MatchPair] = field(default_factory=list)
    aggregate_matches: list[AggregateMatchPair] = field(default_factory=list)
    unmatched_bank: list[int] = field(default_factory=list)
    unmatched_ledger: list[int] = field(default_factory=list)
    stats: dict[str, Any] = field(default_factory=dict)


def run_matching(
    bank_transactions: list[dict],
    ledger_entries: list[dict],
    config: dict[str, Any] | None = None,
) -> MatchResult:
    """Run all matching strategies in priority order.

    1. Exact reference + amount match
    2. Exact amount + date within tolerance
    3. Date proximity + approximate amount
    4. Fuzzy payee name + approximate amount
    5. Aggregate matching (combinations of 2-4 entries)
    """
    cfg = MatchConfig(
        date_tolerance_days=int((config or {}).get("date_tolerance_days", 3)),
        amount_tolerance=float((config or {}).get("amount_tolerance", 1.0)),
        fuzzy_threshold=int((config or {}).get("fuzzy_match_threshold", 80)),
        fx_rate_tolerance_pct=float((config or {}).get("fx_rate_tolerance_pct", 1.0)),
    )

    result = MatchResult()
    strategy_counts: dict[str, int] = {}

    matched_bank: set[int] = set()
    matched_ledger: set[int] = set()

    strategies = [
        ("reference", reference_match),
        ("exact_amount", exact_amount_match),
        ("date_proximity", date_proximity_match),
        ("fuzzy_payee", fuzzy_payee_match),
    ]

    for name, strategy_fn in strategies:
        remaining_bank = [b for b in bank_transactions if b["id"] not in matched_bank]
        remaining_ledger = [le for le in ledger_entries if le["id"] not in matched_ledger]

        if not remaining_bank or not remaining_ledger:
            break

        matches = strategy_fn(remaining_bank, remaining_ledger, cfg)

        for bank_id, ledger_id, confidence, strategy in matches:
            if bank_id in matched_bank or ledger_id in matched_ledger:
                continue
            result.matches.append(MatchPair(
                bank_id=bank_id,
                ledger_id=ledger_id,
                confidence=confidence,
                strategy=strategy,
            ))
            matched_bank.add(bank_id)
            matched_ledger.add(ledger_id)
            strategy_counts[strategy] = strategy_counts.get(strategy, 0) + 1

    remaining_bank = [b for b in bank_transactions if b["id"] not in matched_bank]
    remaining_ledger = [le for le in ledger_entries if le["id"] not in matched_ledger]

    if remaining_bank and remaining_ledger:
        agg_matches = aggregate_match(remaining_bank, remaining_ledger, cfg)
        for bank_ids, ledger_id, confidence, strategy in agg_matches:
            if ledger_id in matched_ledger:
                continue
            if any(bid in matched_bank for bid in bank_ids):
                continue

            result.aggregate_matches.append(AggregateMatchPair(
                bank_ids=bank_ids,
                ledger_id=ledger_id,
                confidence=confidence,
                strategy=strategy,
            ))
            matched_bank.update(bank_ids)
            matched_ledger.add(ledger_id)
            strategy_counts["aggregate"] = strategy_counts.get("aggregate", 0) + 1

    result.unmatched_bank = [b["id"] for b in bank_transactions if b["id"] not in matched_bank]
    result.unmatched_ledger = [le["id"] for le in ledger_entries if le["id"] not in matched_ledger]

    result.stats = {
        "total_bank": len(bank_transactions),
        "total_ledger": len(ledger_entries),
        "matched": len(result.matches) + len(result.aggregate_matches),
        "unmatched_bank": len(result.unmatched_bank),
        "unmatched_ledger": len(result.unmatched_ledger),
        "by_strategy": strategy_counts,
    }

    return result
