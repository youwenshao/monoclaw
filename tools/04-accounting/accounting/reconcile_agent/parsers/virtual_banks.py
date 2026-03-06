"""Virtual bank CSV statement parsers for ZA Bank, Mox Bank, and Livi Bank.

All three export relatively simple CSVs with Date, Description, Amount
(or Debit/Credit), and Balance columns.
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

_DATE_FORMATS = ["%Y-%m-%d", "%d/%m/%Y", "%Y/%m/%d", "%d-%m-%Y"]


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


def _detect_bank_name(text: str) -> str | None:
    snippet = text[:2048].lower()
    if "za bank" in snippet or "众安银行" in snippet:
        return "ZA Bank"
    if "mox bank" in snippet or "mox" in snippet:
        return "Mox"
    if "livi bank" in snippet or "livi" in snippet:
        return "Livi"
    return None


def _parse_virtual_bank_csv(file_path: Path, bank_name: str) -> ParseResult:
    text = file_path.read_text(encoding="utf-8-sig", errors="replace")
    reader = csv.DictReader(text.splitlines())
    fieldnames = list(reader.fieldnames or [])
    norm_map = {_normalise(f): f for f in fieldnames}

    date_col = norm_map.get("date") or norm_map.get("transaction date")
    desc_col = norm_map.get("description") or norm_map.get("details") or norm_map.get("remarks")
    amount_col = norm_map.get("amount")
    debit_col = norm_map.get("debit") or norm_map.get("withdrawal")
    credit_col = norm_map.get("credit") or norm_map.get("deposit")
    balance_col = norm_map.get("balance")

    if not date_col:
        raise ValueError(f"{bank_name} CSV missing date column")
    if not desc_col:
        raise ValueError(f"{bank_name} CSV missing description column")

    single_amount = amount_col is not None and debit_col is None

    transactions: list[Transaction] = []
    warnings: list[str] = []

    for line_no, row in enumerate(reader, start=2):
        raw_date = row.get(date_col, "").strip()
        if not raw_date:
            continue

        try:
            txn_date = _parse_date(raw_date)
        except ValueError:
            warnings.append(f"Line {line_no}: unparseable date {raw_date!r}")
            continue

        description = row.get(desc_col, "").strip()
        if not description:
            continue

        if single_amount:
            amount = _parse_amount(row.get(amount_col or "", "0"))
            debit = abs(amount) if amount < 0 else 0.0
            credit = amount if amount > 0 else 0.0
        else:
            debit = _parse_amount(row.get(debit_col or "", "0"))
            credit = _parse_amount(row.get(credit_col or "", "0"))

        balance_raw = row.get(balance_col or "", "").strip() if balance_col else ""
        balance = _parse_amount(balance_raw) if balance_raw else None

        txn_type: str | None = None
        desc_upper = description.upper()
        if "FPS" in desc_upper:
            txn_type = "fps"
        elif "TRANSFER" in desc_upper:
            txn_type = "transfer"
        elif "INTEREST" in desc_upper:
            txn_type = "interest"
        elif "FEE" in desc_upper or "CHARGE" in desc_upper:
            txn_type = "charge"

        transactions.append(Transaction(
            transaction_date=txn_date,
            value_date=None,
            description=description,
            reference=None,
            debit=debit,
            credit=credit,
            balance=balance,
            currency="HKD",
            transaction_type=txn_type,
        ))

    closing = transactions[-1].balance if transactions and transactions[-1].balance is not None else None

    return ParseResult(
        transactions=transactions,
        bank_name=bank_name,
        currency="HKD",
        closing_balance=closing,
        warnings=warnings,
    )


@register_parser
class ZABankParser(BaseStatementParser):
    bank_name = "ZA Bank"

    def detect(self, file_path: Path) -> bool:
        if file_path.suffix.lower() not in (".csv",):
            return False
        try:
            text = file_path.read_text(encoding="utf-8-sig", errors="replace")
        except Exception:
            return False
        return _detect_bank_name(text) == "ZA Bank"

    def parse(self, file_path: Path) -> ParseResult:
        return _parse_virtual_bank_csv(file_path, self.bank_name)


@register_parser
class MoxParser(BaseStatementParser):
    bank_name = "Mox"

    def detect(self, file_path: Path) -> bool:
        if file_path.suffix.lower() not in (".csv",):
            return False
        try:
            text = file_path.read_text(encoding="utf-8-sig", errors="replace")
        except Exception:
            return False
        return _detect_bank_name(text) == "Mox"

    def parse(self, file_path: Path) -> ParseResult:
        return _parse_virtual_bank_csv(file_path, self.bank_name)


@register_parser
class LiviParser(BaseStatementParser):
    bank_name = "Livi"

    def detect(self, file_path: Path) -> bool:
        if file_path.suffix.lower() not in (".csv",):
            return False
        try:
            text = file_path.read_text(encoding="utf-8-sig", errors="replace")
        except Exception:
            return False
        return _detect_bank_name(text) == "Livi"

    def parse(self, file_path: Path) -> ParseResult:
        return _parse_virtual_bank_csv(file_path, self.bank_name)
