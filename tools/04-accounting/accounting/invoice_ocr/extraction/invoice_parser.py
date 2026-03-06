"""Parse OCR raw text into structured invoice data."""

from __future__ import annotations

import re
from typing import Any


_AMOUNT_PATTERN = re.compile(
    r"(?:HK\$|HKD|USD|RMB|CNY|EUR|GBP|¥|\$)?\s*([\d,]+\.\d{2})",
    re.IGNORECASE,
)
_DATE_PATTERNS = [
    re.compile(r"(\d{4}[-/]\d{1,2}[-/]\d{1,2})"),
    re.compile(r"(\d{1,2}[-/]\d{1,2}[-/]\d{4})"),
    re.compile(r"(\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{4})", re.IGNORECASE),
]
_INVOICE_NUM_PATTERN = re.compile(
    r"(?:Invoice\s*(?:No\.?|Number|#)|Inv[\s.#-]*No\.?)\s*:?\s*([A-Z0-9][\w\-/]{2,})",
    re.IGNORECASE,
)
_SUPPLIER_PATTERNS = [
    re.compile(r"(?:From|Supplier|Vendor|Bill\s*From)\s*:?\s*(.+)", re.IGNORECASE),
    re.compile(r"^([A-Z][A-Za-z\s&.']+(?:Ltd\.?|Limited|Inc\.?|Corp\.?|Co\.?))\s*$", re.IGNORECASE | re.MULTILINE),
]
_CURRENCY_PATTERN = re.compile(r"\b(HKD|USD|RMB|CNY|EUR|GBP)\b", re.IGNORECASE)

_TOTAL_KEYWORDS = re.compile(
    r"(?:Grand\s*)?Total\s*(?:Due|Amount|Payable)?\s*:?\s*",
    re.IGNORECASE,
)
_SUBTOTAL_KEYWORDS = re.compile(r"Sub\s*-?\s*Total\s*:?\s*", re.IGNORECASE)
_TAX_KEYWORDS = re.compile(r"(?:Tax|VAT|GST)\s*(?:\(\d+%?\))?\s*:?\s*", re.IGNORECASE)
_DUE_DATE_KEYWORDS = re.compile(r"(?:Due\s*Date|Payment\s*Due)\s*:?\s*", re.IGNORECASE)


def _extract_amount(text: str) -> float | None:
    """Extract the first monetary amount from text."""
    m = _AMOUNT_PATTERN.search(text)
    if m:
        try:
            return float(m.group(1).replace(",", ""))
        except ValueError:
            pass
    return None


def _extract_date(text: str) -> str | None:
    """Extract the first date from text."""
    for pattern in _DATE_PATTERNS:
        m = pattern.search(text)
        if m:
            return m.group(1)
    return None


def parse_invoice(ocr_result: dict[str, Any]) -> dict[str, Any]:
    """Parse OCR output into structured invoice fields.

    Args:
        ocr_result: Dict with 'raw_text' and 'blocks' from the vision engine.

    Returns dict with: supplier_name, invoice_number, invoice_date, due_date,
    line_items, subtotal, tax_amount, total_amount, currency.
    """
    raw_text = ocr_result.get("raw_text", "")
    blocks = ocr_result.get("blocks", [])

    result: dict[str, Any] = {
        "supplier_name": None,
        "invoice_number": None,
        "invoice_date": None,
        "due_date": None,
        "line_items": [],
        "subtotal": None,
        "tax_amount": None,
        "total_amount": None,
        "currency": "HKD",
    }

    m = _CURRENCY_PATTERN.search(raw_text)
    if m:
        result["currency"] = m.group(1).upper()

    m = _INVOICE_NUM_PATTERN.search(raw_text)
    if m:
        result["invoice_number"] = m.group(1).strip()

    for pattern in _SUPPLIER_PATTERNS:
        m = pattern.search(raw_text)
        if m:
            result["supplier_name"] = m.group(1).strip().rstrip(".")
            break

    lines = raw_text.split("\n")
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        if _DUE_DATE_KEYWORDS.search(stripped):
            d = _extract_date(_DUE_DATE_KEYWORDS.sub("", stripped))
            if d:
                result["due_date"] = d
                continue

        if result["invoice_date"] is None and re.search(r"(?:Date|日期)", stripped, re.IGNORECASE):
            d = _extract_date(stripped)
            if d:
                result["invoice_date"] = d
                continue

        if _TOTAL_KEYWORDS.search(stripped) and not _SUBTOTAL_KEYWORDS.search(stripped):
            amt = _extract_amount(stripped)
            if amt is not None:
                result["total_amount"] = amt
                continue

        if _SUBTOTAL_KEYWORDS.search(stripped):
            amt = _extract_amount(stripped)
            if amt is not None:
                result["subtotal"] = amt
                continue

        if _TAX_KEYWORDS.search(stripped):
            amt = _extract_amount(stripped)
            if amt is not None:
                result["tax_amount"] = amt
                continue

    if result["invoice_date"] is None:
        result["invoice_date"] = _extract_date(raw_text)

    if blocks:
        from accounting.invoice_ocr.ocr.line_extractor import extract_line_items
        result["line_items"] = extract_line_items(blocks)

    if result["total_amount"] is None and result["subtotal"] is not None:
        tax = result["tax_amount"] or 0.0
        result["total_amount"] = round(result["subtotal"] + tax, 2)

    if result["subtotal"] is None and result["total_amount"] is not None:
        tax = result["tax_amount"] or 0.0
        result["subtotal"] = round(result["total_amount"] - tax, 2)

    return result
