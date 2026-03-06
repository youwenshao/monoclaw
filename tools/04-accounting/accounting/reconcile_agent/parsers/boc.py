"""Bank of China (Hong Kong) CSV statement parser.

BOC exports use bilingual column headers and DD/MM/YYYY date format.
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

_DATE_FORMATS = ["%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d"]


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
    "date": ["date", "transaction date", "交易日期", "日期"],
    "value_date": ["value date", "起息日", "入帳日期"],
    "description": ["description", "details", "摘要", "交易描述", "描述"],
    "debit": ["debit", "withdrawal", "debit amount", "支出", "支出金額"],
    "credit": ["credit", "deposit", "credit amount", "存入", "存入金額"],
    "balance": ["balance", "結餘", "余额", "帳戶結餘"],
    "reference": ["reference", "ref", "cheque no", "參考編號", "支票號碼"],
    "currency": ["currency", "ccy", "幣種"],
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
class BOCParser(BaseStatementParser):
    bank_name = "Bank of China"

    def detect(self, file_path: Path) -> bool:
        if file_path.suffix.lower() not in (".csv", ".tsv"):
            return False
        try:
            text = file_path.read_text(encoding="utf-8-sig", errors="replace")
        except Exception:
            return False

        snippet = text[:2048]
        if "bank of china" in snippet.lower() or "中國銀行" in snippet or "中银" in snippet:
            return True

        first_line = text.split("\n", 1)[0]
        headers = {_normalise(h) for h in first_line.split(",")}
        boc_markers = {"交易日期", "摘要", "支出金額", "存入金額"}
        if boc_markers & headers:
            return True

        return False

    def parse(self, file_path: Path) -> ParseResult:
        text = file_path.read_text(encoding="utf-8-sig", errors="replace")

        lines = text.splitlines()
        header_idx = 0
        for i, line in enumerate(lines):
            norm = _normalise(line)
            if "date" in norm or "日期" in line:
                header_idx = i
                break

        reader = csv.DictReader(lines[header_idx:])
        cols = _resolve_columns(list(reader.fieldnames or []))

        if not cols["date"] or not cols["description"]:
            raise ValueError("BOC CSV missing required date/description columns")

        transactions: list[Transaction] = []
        warnings: list[str] = []
        detected_currency = "HKD"

        for line_no, row in enumerate(reader, start=header_idx + 2):
            raw_date = row.get(cols["date"] or "", "").strip()
            if not raw_date:
                continue

            try:
                txn_date = _parse_date(raw_date)
            except ValueError:
                warnings.append(f"Line {line_no}: unparseable date {raw_date!r}")
                continue

            value_date: date | None = None
            if cols["value_date"]:
                vd_raw = row.get(cols["value_date"] or "", "").strip()
                if vd_raw:
                    try:
                        value_date = _parse_date(vd_raw)
                    except ValueError:
                        pass

            description = row.get(cols["description"] or "", "").strip()
            if not description:
                continue

            debit = _parse_amount(row.get(cols["debit"] or "", "0"))
            credit = _parse_amount(row.get(cols["credit"] or "", "0"))
            balance_raw = row.get(cols["balance"] or "", "").strip() if cols["balance"] else ""
            balance = _parse_amount(balance_raw) if balance_raw else None
            reference = row.get(cols["reference"] or "", "").strip() if cols["reference"] else None

            if cols["currency"]:
                ccy = row.get(cols["currency"] or "", "").strip().upper()
                if ccy:
                    detected_currency = ccy

            txn_type: str | None = None
            desc_upper = description.upper()
            if "FPS" in desc_upper or "轉數快" in description:
                txn_type = "fps"
            elif "AUTOPAY" in desc_upper or "自動轉帳" in description:
                txn_type = "autopay"
            elif "CHQ" in desc_upper or "支票" in description:
                txn_type = "cheque"
            elif desc_upper.startswith("TT") or "電匯" in description:
                txn_type = "tt"
            elif "SERVICE CHARGE" in desc_upper or "手續費" in description:
                txn_type = "charge"

            transactions.append(Transaction(
                transaction_date=txn_date,
                value_date=value_date,
                description=description,
                reference=reference,
                debit=debit,
                credit=credit,
                balance=balance,
                currency=detected_currency,
                transaction_type=txn_type,
            ))

        closing = transactions[-1].balance if transactions and transactions[-1].balance is not None else None

        return ParseResult(
            transactions=transactions,
            bank_name=self.bank_name,
            currency=detected_currency,
            closing_balance=closing,
            warnings=warnings,
        )
