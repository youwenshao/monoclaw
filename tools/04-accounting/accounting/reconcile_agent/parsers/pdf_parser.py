"""PDF bank statement table extractor using pdfplumber.

Attempts to find the main transaction table on each page, extract rows,
and normalise them into Transaction objects.
"""

from __future__ import annotations

import re
from datetime import datetime, date
from pathlib import Path

from .base import (
    BaseStatementParser,
    ParseResult,
    Transaction,
    register_parser,
)

_DATE_PATTERN = re.compile(r"\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4}")
_DATE_FORMATS = ["%d/%m/%Y", "%d/%m/%y", "%d-%m-%Y", "%d-%m-%y", "%Y-%m-%d"]


def _try_parse_date(raw: str) -> date | None:
    raw = raw.strip()
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    return None


def _parse_amount(raw: str) -> float:
    cleaned = re.sub(r"[^\d.\-]", "", raw.strip())
    if not cleaned:
        return 0.0
    return float(cleaned)


def _detect_bank_from_text(text: str) -> str:
    lower = text.lower()
    bank_markers = [
        ("hsbc", "HSBC"),
        ("hang seng", "Hang Seng"),
        ("恒生", "Hang Seng"),
        ("bank of china", "Bank of China"),
        ("中國銀行", "Bank of China"),
        ("standard chartered", "Standard Chartered"),
        ("za bank", "ZA Bank"),
        ("mox", "Mox"),
        ("livi", "Livi"),
        ("dbs", "DBS"),
        ("citibank", "Citibank"),
    ]
    for marker, name in bank_markers:
        if marker in lower:
            return name
    return "Unknown"


def _identify_columns(header_cells: list[str]) -> dict[str, int | None]:
    """Map semantic column names to table column indices."""
    mapping: dict[str, int | None] = {
        "date": None,
        "description": None,
        "debit": None,
        "credit": None,
        "amount": None,
        "balance": None,
    }

    for i, cell in enumerate(header_cells):
        lower = (cell or "").lower().strip()
        if "date" in lower and mapping["date"] is None:
            mapping["date"] = i
        elif lower in ("description", "details", "particulars", "narrative", "描述", "摘要"):
            mapping["description"] = i
        elif lower in ("debit", "withdrawal", "dr", "支出"):
            mapping["debit"] = i
        elif lower in ("credit", "deposit", "cr", "存入"):
            mapping["credit"] = i
        elif lower == "amount":
            mapping["amount"] = i
        elif "balance" in lower or "結餘" in lower:
            mapping["balance"] = i

    return mapping


@register_parser
class PDFStatementParser(BaseStatementParser):
    bank_name = "PDF"

    def detect(self, file_path: Path) -> bool:
        return file_path.suffix.lower() == ".pdf"

    def parse(self, file_path: Path) -> ParseResult:
        import pdfplumber

        transactions: list[Transaction] = []
        warnings: list[str] = []
        bank_name = "Unknown"
        full_text_sample = ""

        with pdfplumber.open(str(file_path)) as pdf:
            if pdf.pages:
                full_text_sample = pdf.pages[0].extract_text() or ""
                bank_name = _detect_bank_from_text(full_text_sample)

            for page_num, page in enumerate(pdf.pages, start=1):
                tables = page.extract_tables()
                if not tables:
                    continue

                for table in tables:
                    if not table or len(table) < 2:
                        continue

                    header_row = table[0]
                    cols = _identify_columns([c or "" for c in header_row])

                    if cols["date"] is None:
                        has_date = False
                        for row in table[1:3]:
                            if row and any(_DATE_PATTERN.search(str(c or "")) for c in row):
                                has_date = True
                                break
                        if not has_date:
                            continue
                        cols["date"] = 0
                        if cols["description"] is None and len(header_row) > 1:
                            cols["description"] = 1

                    single_amount = cols["amount"] is not None and cols["debit"] is None

                    for row_idx, row in enumerate(table[1:], start=2):
                        if not row or all(not c for c in row):
                            continue

                        date_val = str(row[cols["date"]] or "").strip() if cols["date"] is not None else ""
                        txn_date = _try_parse_date(date_val) if date_val else None
                        if not txn_date:
                            continue

                        desc_idx = cols["description"]
                        description = str(row[desc_idx] or "").strip() if desc_idx is not None and desc_idx < len(row) else ""

                        if single_amount and cols["amount"] is not None:
                            amt_raw = str(row[cols["amount"]] or "0") if cols["amount"] < len(row) else "0"
                            amount = _parse_amount(amt_raw)
                            debit = abs(amount) if amount < 0 else 0.0
                            credit = amount if amount > 0 else 0.0
                        else:
                            dr_idx = cols["debit"]
                            cr_idx = cols["credit"]
                            debit = _parse_amount(str(row[dr_idx] or "0")) if dr_idx is not None and dr_idx < len(row) else 0.0
                            credit = _parse_amount(str(row[cr_idx] or "0")) if cr_idx is not None and cr_idx < len(row) else 0.0

                        bal_idx = cols["balance"]
                        balance = _parse_amount(str(row[bal_idx] or "")) if bal_idx is not None and bal_idx < len(row) and str(row[bal_idx] or "").strip() else None

                        transactions.append(Transaction(
                            transaction_date=txn_date,
                            value_date=None,
                            description=description,
                            reference=None,
                            debit=debit,
                            credit=credit,
                            balance=balance,
                            currency="HKD",
                            transaction_type=None,
                        ))

        if not transactions:
            warnings.append("No transaction tables found in PDF")

        closing = transactions[-1].balance if transactions and transactions[-1].balance is not None else None

        return ParseResult(
            transactions=transactions,
            bank_name=bank_name,
            currency="HKD",
            closing_balance=closing,
            warnings=warnings,
        )
