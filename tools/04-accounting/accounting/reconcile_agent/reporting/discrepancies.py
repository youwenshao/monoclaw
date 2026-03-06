"""Categorise unmatched reconciliation items and generate a prioritised
discrepancy list for human review.

Categories:
- bank_charge: Bank fees/charges not yet recorded in books
- outstanding_cheque: Cheques issued but not yet presented
- deposit_in_transit: Deposits recorded in books, pending bank clearance
- timing_difference: Entries that will likely clear within a few days
- missing_entry: Items present in one side only, requiring investigation
- duplicate: Potential duplicate transactions
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any


@dataclass
class Discrepancy:
    entry_id: int
    source: str  # "bank" or "ledger"
    category: str
    priority: int  # 1=high, 2=medium, 3=low
    description: str
    amount: float
    transaction_date: date | None
    suggested_action: str
    auto_resolvable: bool = False


@dataclass
class DiscrepancyReport:
    reconciliation_id: int | None
    as_of_date: date
    items: list[Discrepancy] = field(default_factory=list)
    summary: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "reconciliation_id": self.reconciliation_id,
            "as_of_date": self.as_of_date.isoformat(),
            "total_discrepancies": len(self.items),
            "by_priority": {
                "high": sum(1 for d in self.items if d.priority == 1),
                "medium": sum(1 for d in self.items if d.priority == 2),
                "low": sum(1 for d in self.items if d.priority == 3),
            },
            "by_category": self.summary.get("by_category", {}),
            "total_amount": sum(d.amount for d in self.items),
            "auto_resolvable_count": sum(1 for d in self.items if d.auto_resolvable),
            "items": [
                {
                    "entry_id": d.entry_id,
                    "source": d.source,
                    "category": d.category,
                    "priority": d.priority,
                    "description": d.description,
                    "amount": d.amount,
                    "transaction_date": d.transaction_date.isoformat() if d.transaction_date else None,
                    "suggested_action": d.suggested_action,
                    "auto_resolvable": d.auto_resolvable,
                }
                for d in sorted(self.items, key=lambda x: (x.priority, -x.amount))
            ],
        }


def _parse_date(raw: Any) -> date | None:
    if isinstance(raw, date):
        return raw
    if isinstance(raw, str):
        try:
            return date.fromisoformat(raw)
        except ValueError:
            return None
    return None


def _classify_bank_entry(entry: dict[str, Any], as_of: date) -> Discrepancy:
    """Classify an unmatched bank transaction."""
    debit = float(entry.get("debit", 0) or 0)
    credit = float(entry.get("credit", 0) or 0)
    amount = max(debit, credit)
    desc = entry.get("description", "")
    txn_type = (entry.get("transaction_type") or "").lower()
    txn_date = _parse_date(entry.get("transaction_date"))

    if txn_type in ("charge", "fee") or "fee" in desc.lower() or "charge" in desc.lower() or "maintenance" in desc.lower():
        return Discrepancy(
            entry_id=entry["id"], source="bank", category="bank_charge",
            priority=3, description=desc, amount=amount,
            transaction_date=txn_date,
            suggested_action="Record bank charge in ledger",
            auto_resolvable=True,
        )

    if txn_type == "interest" or "interest" in desc.lower():
        return Discrepancy(
            entry_id=entry["id"], source="bank", category="bank_charge",
            priority=3, description=desc, amount=amount,
            transaction_date=txn_date,
            suggested_action="Record bank interest in ledger",
            auto_resolvable=True,
        )

    if txn_date and (as_of - txn_date).days <= 3:
        return Discrepancy(
            entry_id=entry["id"], source="bank", category="timing_difference",
            priority=2, description=desc, amount=amount,
            transaction_date=txn_date,
            suggested_action="Likely clears in next reconciliation period",
            auto_resolvable=False,
        )

    return Discrepancy(
        entry_id=entry["id"], source="bank", category="missing_entry",
        priority=1, description=desc, amount=amount,
        transaction_date=txn_date,
        suggested_action="Investigate — bank transaction has no matching ledger entry",
        auto_resolvable=False,
    )


def _classify_ledger_entry(entry: dict[str, Any], as_of: date) -> Discrepancy:
    """Classify an unmatched ledger entry."""
    debit = float(entry.get("debit", 0) or 0)
    credit = float(entry.get("credit", 0) or 0)
    amount = max(debit, credit)
    desc = entry.get("description", "")
    txn_date = _parse_date(entry.get("entry_date"))

    if "cheque" in desc.lower() or "chq" in desc.lower():
        return Discrepancy(
            entry_id=entry["id"], source="ledger", category="outstanding_cheque",
            priority=2, description=desc, amount=amount,
            transaction_date=txn_date,
            suggested_action="Cheque not yet presented — follow up if stale",
            auto_resolvable=False,
        )

    if credit > 0:
        return Discrepancy(
            entry_id=entry["id"], source="ledger", category="deposit_in_transit",
            priority=2, description=desc, amount=amount,
            transaction_date=txn_date,
            suggested_action="Deposit recorded in books, awaiting bank clearance",
            auto_resolvable=False,
        )

    if txn_date and (as_of - txn_date).days <= 3:
        return Discrepancy(
            entry_id=entry["id"], source="ledger", category="timing_difference",
            priority=3, description=desc, amount=amount,
            transaction_date=txn_date,
            suggested_action="Recent entry — likely appears in next bank statement",
            auto_resolvable=False,
        )

    return Discrepancy(
        entry_id=entry["id"], source="ledger", category="missing_entry",
        priority=1, description=desc, amount=amount,
        transaction_date=txn_date,
        suggested_action="Investigate — ledger entry has no matching bank transaction",
        auto_resolvable=False,
    )


def _detect_duplicates(entries: list[dict[str, Any]], source: str) -> list[Discrepancy]:
    """Scan for potential duplicate entries (same amount + date + similar description)."""
    from rapidfuzz import fuzz

    duplicates: list[Discrepancy] = []
    seen: list[dict[str, Any]] = []

    date_key = "transaction_date" if source == "bank" else "entry_date"

    for entry in entries:
        amount = max(float(entry.get("debit", 0) or 0), float(entry.get("credit", 0) or 0))
        entry_date = _parse_date(entry.get(date_key))
        desc = entry.get("description", "")

        for prev in seen:
            prev_amount = max(float(prev.get("debit", 0) or 0), float(prev.get("credit", 0) or 0))
            prev_date = _parse_date(prev.get(date_key))
            prev_desc = prev.get("description", "")

            if (
                abs(amount - prev_amount) < 0.01
                and entry_date == prev_date
                and fuzz.ratio(desc.upper(), prev_desc.upper()) > 90
            ):
                duplicates.append(Discrepancy(
                    entry_id=entry["id"], source=source, category="duplicate",
                    priority=1, description=f"Possible duplicate of #{prev['id']}: {desc}",
                    amount=amount, transaction_date=entry_date,
                    suggested_action=f"Compare with entry #{prev['id']} — may be duplicate",
                    auto_resolvable=False,
                ))
                break

        seen.append(entry)

    return duplicates


def generate_discrepancy_report(
    unmatched_bank: list[dict[str, Any]],
    unmatched_ledger: list[dict[str, Any]],
    reconciliation_id: int | None = None,
    as_of_date: date | None = None,
) -> DiscrepancyReport:
    """Generate a categorised, prioritised discrepancy report."""
    as_of = as_of_date or date.today()

    report = DiscrepancyReport(
        reconciliation_id=reconciliation_id,
        as_of_date=as_of,
    )

    for b in unmatched_bank:
        report.items.append(_classify_bank_entry(b, as_of))

    for le in unmatched_ledger:
        report.items.append(_classify_ledger_entry(le, as_of))

    report.items.extend(_detect_duplicates(unmatched_bank, "bank"))
    report.items.extend(_detect_duplicates(unmatched_ledger, "ledger"))

    by_category: dict[str, int] = {}
    for d in report.items:
        by_category[d.category] = by_category.get(d.category, 0) + 1
    report.summary["by_category"] = by_category

    return report
