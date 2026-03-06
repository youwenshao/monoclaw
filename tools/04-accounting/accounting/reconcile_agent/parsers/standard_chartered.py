"""Standard Chartered Bank Hong Kong CSV statement parser.

StanChart exports typically have Date, Description, Debit, Credit, Balance
columns in English.
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

_DATE_FORMATS = ["%d/%m/%Y", "%d %b %Y", "%d-%m-%Y", "%Y-%m-%d"]


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
    "date": ["date", "transaction date", "posting date", "value date"],
    "description": ["description", "details", "particulars", "narrative"],
    "debit": ["debit", "debit amount", "withdrawal", "dr"],
    "credit": ["credit", "credit amount", "deposit", "cr"],
    "balance": ["balance", "running balance", "available balance"],
    "reference": ["reference", "ref", "cheque no"],
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
class StandardCharteredParser(BaseStatementParser):
    bank_name = "Standard Chartered"

    def detect(self, file_path: Path) -> bool:
        if file_path.suffix.lower() not in (".csv", ".tsv"):
            return False
        try:
            text = file_path.read_text(encoding="utf-8-sig", errors="replace")
        except Exception:
            return False

        snippet = text[:2048].lower()
        if "standard chartered" in snippet or "scb" in snippet:
            return True

        first_line = text.split("\n", 1)[0]
        headers = {_normalise(h) for h in first_line.split(",")}
        sc_markers = {"particulars", "narrative"}
        return bool(sc_markers & headers)

    def parse(self, file_path: Path) -> ParseResult:
        text = file_path.read_text(encoding="utf-8-sig", errors="replace")
        reader = csv.DictReader(text.splitlines())
        cols = _resolve_columns(list(reader.fieldnames or []))

        if not cols["date"] or not cols["description"]:
            raise ValueError("Standard Chartered CSV missing required date/description columns")

        transactions: list[Transaction] = []
        warnings: list[str] = []

        for line_no, row in enumerate(reader, start=2):
            raw_date = row.get(cols["date"] or "", "").strip()
            if not raw_date:
                continue

            try:
                txn_date = _parse_date(raw_date)
            except ValueError:
                warnings.append(f"Line {line_no}: unparseable date {raw_date!r}")
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
            if "FPS" in desc_upper or "FASTER PAYMENT" in desc_upper:
                txn_type = "fps"
            elif "AUTOPAY" in desc_upper or "AUTO PAY" in desc_upper:
                txn_type = "autopay"
            elif "CHQ" in desc_upper or "CHEQUE" in desc_upper:
                txn_type = "cheque"
            elif desc_upper.startswith("TT ") or "TELEGRAPHIC" in desc_upper:
                txn_type = "tt"
            elif "SERVICE CHARGE" in desc_upper or "FEE" in desc_upper:
                txn_type = "charge"
            elif "INTEREST" in desc_upper:
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

        closing = transactions[-1].balance if transactions and transactions[-1].balance is not None else None

        return ParseResult(
            transactions=transactions,
            bank_name=self.bank_name,
            currency="HKD",
            closing_balance=closing,
            warnings=warnings,
        )
