"""Hang Seng Bank CSV statement parser.

Hang Seng exports group transactions by date with separate Debit/Credit
columns.  Descriptions may be in Chinese or bilingual.
"""

from __future__ import annotations

import csv
from datetime import datetime, date
from pathlib import Path

from .base import (
    BaseStatementParser,
    ParseResult,
    Transaction,
    register_parser,
)

_DATE_FORMATS = ["%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d", "%Y/%m/%d"]

HANG_SENG_HEADER_VARIANTS = [
    {"date", "description", "debit", "credit"},
    {"日期", "描述", "支出", "存入"},
    {"transaction date", "details", "debit", "credit"},
]


def _parse_date(raw: str) -> date:
    raw = raw.strip()
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Cannot parse date: {raw!r}")


def _parse_amount(raw: str) -> float:
    cleaned = raw.strip().replace(",", "").replace(" ", "")
    if not cleaned or cleaned == "-":
        return 0.0
    return float(cleaned)


def _normalise(h: str) -> str:
    return h.strip().lower().replace("_", " ")


_COLUMN_ALIASES = {
    "date": ["date", "transaction date", "日期"],
    "description": ["description", "details", "描述", "交易描述"],
    "debit": ["debit", "withdrawal", "支出"],
    "credit": ["credit", "deposit", "存入"],
    "balance": ["balance", "結餘", "余额"],
    "reference": ["reference", "ref", "參考編號"],
}


def _resolve_columns(fieldnames: list[str]) -> dict[str, str | None]:
    norm_map = {_normalise(f): f for f in fieldnames}
    resolved: dict[str, str | None] = {}
    for key, aliases in _COLUMN_ALIASES.items():
        resolved[key] = None
        for alias in aliases:
            if alias in norm_map:
                resolved[key] = norm_map[alias]
                break
    return resolved


@register_parser
class HangSengParser(BaseStatementParser):
    bank_name = "Hang Seng"

    def detect(self, file_path: Path) -> bool:
        if file_path.suffix.lower() not in (".csv", ".tsv"):
            return False
        try:
            text = file_path.read_text(encoding="utf-8-sig", errors="replace")
        except Exception:
            return False

        lower = text[:2048].lower()
        if "hang seng" in lower or "恒生" in text[:2048]:
            return True

        first_line = text.split("\n", 1)[0]
        headers = {_normalise(h) for h in first_line.split(",")}
        return any(variant <= headers for variant in HANG_SENG_HEADER_VARIANTS)

    def parse(self, file_path: Path) -> ParseResult:
        text = file_path.read_text(encoding="utf-8-sig", errors="replace")
        reader = csv.DictReader(text.splitlines())
        cols = _resolve_columns(list(reader.fieldnames or []))

        if not cols["date"] or not cols["description"]:
            raise ValueError("Hang Seng CSV missing required date/description columns")

        transactions: list[Transaction] = []
        warnings: list[str] = []
        current_date: date | None = None

        for line_no, row in enumerate(reader, start=2):
            raw_date = row.get(cols["date"] or "", "").strip()
            if raw_date:
                try:
                    current_date = _parse_date(raw_date)
                except ValueError:
                    warnings.append(f"Line {line_no}: unparseable date {raw_date!r}")
                    continue

            if current_date is None:
                continue

            description = row.get(cols["description"] or "", "").strip()
            if not description:
                continue

            debit = _parse_amount(row.get(cols["debit"] or "", "0"))
            credit = _parse_amount(row.get(cols["credit"] or "", "0"))
            balance_raw = row.get(cols["balance"] or "", "").strip() if cols["balance"] else ""
            balance = _parse_amount(balance_raw) if balance_raw else None
            reference = row.get(cols["reference"] or "", "").strip() if cols["reference"] else None

            txn_type: str | None = None
            desc_upper = description.upper()
            if "FPS" in desc_upper or "轉數快" in description:
                txn_type = "fps"
            elif "AUTOPAY" in desc_upper or "自動轉帳" in description:
                txn_type = "autopay"
            elif "CHQ" in desc_upper or "支票" in description:
                txn_type = "cheque"
            elif desc_upper.startswith("TT ") or "電匯" in description:
                txn_type = "tt"

            transactions.append(Transaction(
                transaction_date=current_date,
                value_date=None,
                description=description,
                reference=reference,
                debit=debit,
                credit=credit,
                balance=balance,
                currency="HKD",
                transaction_type=txn_type,
            ))

        closing = transactions[-1].balance if transactions and transactions[-1].balance is not None else None

        return ParseResult(
            transactions=transactions,
            bank_name=self.bank_name,
            currency="HKD",
            closing_balance=closing,
            warnings=warnings,
        )
