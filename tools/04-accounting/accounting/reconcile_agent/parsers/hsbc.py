"""HSBC Hong Kong CSV statement parser.

HSBC exports use a single Amount column (negative = debit, positive = credit)
with a running balance. FPS transactions are labelled "FASTER PAYMENT".
"""

from __future__ import annotations

import csv
import re
from datetime import datetime, date
from pathlib import Path

from .base import (
    BaseStatementParser,
    ParseResult,
    Transaction,
    register_parser,
)

_DATE_FORMATS = ["%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d"]

HSBC_HEADER_VARIANTS = [
    {"date", "description", "amount"},
    {"date", "description", "amount", "balance"},
    {"transaction date", "description", "amount", "balance"},
    {"posting date", "description", "amount"},
]

FPS_PATTERN = re.compile(r"FASTER\s+PAYMENT", re.IGNORECASE)


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


def _normalise_header(h: str) -> str:
    return h.strip().lower().replace("_", " ")


@register_parser
class HSBCParser(BaseStatementParser):
    bank_name = "HSBC"

    def detect(self, file_path: Path) -> bool:
        if file_path.suffix.lower() not in (".csv", ".tsv"):
            return False
        try:
            text = file_path.read_text(encoding="utf-8-sig", errors="replace")
        except Exception:
            return False

        lower = text[:2048].lower()
        if "hsbc" in lower:
            return True

        first_line = text.split("\n", 1)[0]
        headers = {_normalise_header(h) for h in first_line.split(",")}
        return any(variant <= headers for variant in HSBC_HEADER_VARIANTS)

    def parse(self, file_path: Path) -> ParseResult:
        text = file_path.read_text(encoding="utf-8-sig", errors="replace")
        reader = csv.DictReader(text.splitlines())

        header_map: dict[str, str] = {}
        for original in reader.fieldnames or []:
            norm = _normalise_header(original)
            header_map[norm] = original

        date_col = header_map.get("date") or header_map.get("transaction date") or header_map.get("posting date")
        desc_col = header_map.get("description")
        amount_col = header_map.get("amount")
        balance_col = header_map.get("balance")
        ref_col = header_map.get("reference")

        if not (date_col and desc_col and amount_col):
            raise ValueError("HSBC CSV missing required columns (date, description, amount)")

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

            amount = _parse_amount(row.get(amount_col, "0"))
            description = row.get(desc_col, "").strip()
            balance = _parse_amount(row.get(balance_col, "")) if balance_col and row.get(balance_col, "").strip() else None
            reference = row.get(ref_col, "").strip() if ref_col else None

            debit = abs(amount) if amount < 0 else 0.0
            credit = amount if amount > 0 else 0.0

            txn_type: str | None = None
            if FPS_PATTERN.search(description):
                txn_type = "fps"
            elif "AUTOPAY" in description.upper():
                txn_type = "autopay"
            elif "CHQ" in description.upper() or "CHEQUE" in description.upper():
                txn_type = "cheque"
            elif description.upper().startswith("TT "):
                txn_type = "tt"
            elif "MAINTENANCE FEE" in description.upper() or "SERVICE CHARGE" in description.upper():
                txn_type = "charge"
            elif "INTEREST" in description.upper():
                txn_type = "interest"

            transactions.append(Transaction(
                transaction_date=txn_date,
                value_date=None,
                description=description,
                reference=reference,
                debit=debit,
                credit=credit,
                balance=balance,
                currency="HKD",
                transaction_type=txn_type,
            ))

        closing_balance = transactions[-1].balance if transactions and transactions[-1].balance is not None else None

        return ParseResult(
            transactions=transactions,
            bank_name=self.bank_name,
            currency="HKD",
            closing_balance=closing_balance,
            warnings=warnings,
        )
