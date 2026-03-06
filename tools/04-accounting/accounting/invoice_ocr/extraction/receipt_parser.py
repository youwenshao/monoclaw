"""Simplified parser for handwritten and thermal receipts.

Handles lower-confidence OCR text with fewer structured fields than
a formal invoice. Designed for petty cash receipts, restaurant bills,
taxi receipts, and other informal documents.
"""

from __future__ import annotations

import re
from typing import Any


_AMOUNT_PATTERN = re.compile(r"([\d,]+\.\d{2})")
_DATE_PATTERNS = [
    re.compile(r"(\d{4}[-/]\d{1,2}[-/]\d{1,2})"),
    re.compile(r"(\d{1,2}[-/]\d{1,2}[-/]\d{4})"),
    re.compile(r"(\d{1,2}[-/]\d{1,2}[-/]\d{2})\b"),
]
_TOTAL_KEYWORDS = re.compile(
    r"(?:Total|合計|合计|小計|總計|TOTAL|Amount)\s*:?\s*",
    re.IGNORECASE,
)
_SHOP_NAME_PATTERN = re.compile(
    r"^([A-Z\u4e00-\u9fff][A-Za-z\u4e00-\u9fff\s&.'']{2,})$",
    re.MULTILINE,
)
_RECEIPT_NUM_PATTERN = re.compile(
    r"(?:Receipt|Rcpt|單號|单号)\s*[#:.]?\s*(\w+)",
    re.IGNORECASE,
)


def parse_receipt(ocr_result: dict[str, Any]) -> dict[str, Any]:
    """Parse receipt OCR output into a simplified structure.

    Returns dict with: shop_name, receipt_number, date, total_amount,
    currency, items (list of text lines that look like charges),
    confidence_note.
    """
    raw_text = ocr_result.get("raw_text", "")
    confidence = ocr_result.get("confidence", 0.0)

    result: dict[str, Any] = {
        "shop_name": None,
        "receipt_number": None,
        "date": None,
        "total_amount": None,
        "currency": "HKD",
        "items": [],
        "confidence_note": None,
    }

    if confidence < 0.5:
        result["confidence_note"] = "Very low OCR confidence — manual review strongly recommended"
    elif confidence < 0.7:
        result["confidence_note"] = "Low OCR confidence — verify extracted amounts"

    m = _RECEIPT_NUM_PATTERN.search(raw_text)
    if m:
        result["receipt_number"] = m.group(1).strip()

    m = _SHOP_NAME_PATTERN.search(raw_text)
    if m:
        candidate = m.group(1).strip()
        noise_words = {"INVOICE", "RECEIPT", "TAX", "TOTAL", "DATE", "THANK"}
        if candidate.upper() not in noise_words:
            result["shop_name"] = candidate

    for pattern in _DATE_PATTERNS:
        m = pattern.search(raw_text)
        if m:
            result["date"] = m.group(1)
            break

    amounts: list[float] = []
    lines = raw_text.split("\n")
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        if _TOTAL_KEYWORDS.search(stripped):
            m_amt = _AMOUNT_PATTERN.search(stripped)
            if m_amt:
                try:
                    result["total_amount"] = float(m_amt.group(1).replace(",", ""))
                except ValueError:
                    pass
                continue

        m_amt = _AMOUNT_PATTERN.search(stripped)
        if m_amt:
            try:
                val = float(m_amt.group(1).replace(",", ""))
                amounts.append(val)
                desc = _AMOUNT_PATTERN.sub("", stripped).strip(" .-$*x×X")
                if desc:
                    result["items"].append({"description": desc, "amount": val})
            except ValueError:
                continue

    if result["total_amount"] is None and amounts:
        result["total_amount"] = max(amounts)

    if re.search(r"(USD|US\$|\bUS\b)", raw_text, re.IGNORECASE):
        result["currency"] = "USD"
    elif re.search(r"(RMB|CNY|¥|人民幣|人民币)", raw_text):
        result["currency"] = "RMB"

    return result
