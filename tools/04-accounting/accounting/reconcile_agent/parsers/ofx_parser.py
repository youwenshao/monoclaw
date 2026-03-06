"""Generic OFX/QFX statement parser using ofxparse."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from .base import (
    BaseStatementParser,
    ParseResult,
    Transaction,
    register_parser,
)


def _ofx_date(dt: object) -> date:
    """Convert an ofxparse datetime to a date."""
    if hasattr(dt, "date"):
        return dt.date()  # type: ignore[union-attr]
    return date.today()


def _classify_type(raw_type: str, memo: str) -> str | None:
    rt = raw_type.upper() if raw_type else ""
    memo_upper = memo.upper() if memo else ""

    if rt in ("DEBIT", "CHECK"):
        return "cheque" if "CHQ" in memo_upper or "CHEQUE" in memo_upper else "debit"
    if rt == "CREDIT":
        return "credit"
    if rt == "XFER":
        return "transfer"
    if rt in ("SRVCHG", "FEE"):
        return "charge"
    if rt == "INT":
        return "interest"
    if rt == "ATM":
        return "atm"
    if "FPS" in memo_upper or "FASTER PAYMENT" in memo_upper:
        return "fps"
    return rt.lower() if rt else None


@register_parser
class OFXParser(BaseStatementParser):
    bank_name = "OFX"

    def detect(self, file_path: Path) -> bool:
        suffix = file_path.suffix.lower()
        if suffix in (".ofx", ".qfx"):
            return True
        if suffix not in (".xml", ".sgml"):
            return False
        try:
            header = file_path.read_text(encoding="utf-8", errors="replace")[:512]
            return "OFXHEADER" in header or "<OFX>" in header.upper()
        except Exception:
            return False

    def parse(self, file_path: Path) -> ParseResult:
        import ofxparse

        with open(file_path, "rb") as fh:
            ofx = ofxparse.OfxParser.parse(fh)

        account = ofx.account
        bank_id = getattr(account, "institution", None)
        bank_name_resolved = str(getattr(bank_id, "organization", "")) if bank_id else ""
        if not bank_name_resolved:
            bank_name_resolved = self.bank_name

        currency = getattr(account.statement, "currency", "HKD") or "HKD"

        transactions: list[Transaction] = []
        for stxn in account.statement.transactions:
            amount = float(stxn.amount)
            debit = abs(amount) if amount < 0 else 0.0
            credit = amount if amount > 0 else 0.0

            memo = getattr(stxn, "memo", "") or ""
            payee = getattr(stxn, "payee", "") or ""
            description = f"{payee} {memo}".strip() or getattr(stxn, "name", "") or ""

            transactions.append(Transaction(
                transaction_date=_ofx_date(stxn.date),
                value_date=None,
                description=description,
                reference=getattr(stxn, "id", None) or getattr(stxn, "checknum", None),
                debit=debit,
                credit=credit,
                balance=None,
                currency=currency,
                transaction_type=_classify_type(getattr(stxn, "type", ""), description),
            ))

        closing_balance: float | None = None
        stmt = account.statement
        if hasattr(stmt, "balance"):
            closing_balance = float(stmt.balance)

        return ParseResult(
            transactions=transactions,
            bank_name=bank_name_resolved,
            account_number=getattr(account, "account_id", None),
            currency=currency,
            closing_balance=closing_balance,
            statement_date=_ofx_date(stmt.end_date) if hasattr(stmt, "end_date") and stmt.end_date else None,
        )
