"""Bank statement parser with per-bank templates for HK banks."""

from __future__ import annotations

import re
from typing import Any

BANK_PATTERNS: dict[str, dict[str, re.Pattern[str]]] = {
    "hsbc": {
        "identifier": re.compile(r"HSBC|Hongkong\s+and\s+Shanghai\s+Banking", re.IGNORECASE),
        "account_holder": re.compile(r"(?:Account\s+Holder|Name)\s*:?\s*(.+)", re.IGNORECASE),
        "account_number": re.compile(r"(?:Account\s+(?:No|Number))\s*:?\s*([\d-]+)", re.IGNORECASE),
        "ending_balance": re.compile(r"(?:Ending|Closing)\s+Balance\s*:?\s*(?:HK[D$]\s*)?([0-9,.]+)", re.IGNORECASE),
        "average_balance": re.compile(r"(?:Average|Avg\.?)\s+Balance\s*:?\s*(?:HK[D$]\s*)?([0-9,.]+)", re.IGNORECASE),
        "statement_date": re.compile(r"(?:Statement\s+(?:Date|Period))\s*:?\s*(.+)", re.IGNORECASE),
    },
    "hang_seng": {
        "identifier": re.compile(r"Hang\s+Seng|恒生", re.IGNORECASE),
        "account_holder": re.compile(r"(?:Account\s+Holder|Customer\s+Name)\s*:?\s*(.+)", re.IGNORECASE),
        "account_number": re.compile(r"(?:Account\s+(?:No|Number))\s*:?\s*([\d-]+)", re.IGNORECASE),
        "ending_balance": re.compile(r"(?:Ending|Closing|結餘)\s+(?:Balance)?\s*:?\s*(?:HK[D$]\s*)?([0-9,.]+)", re.IGNORECASE),
        "average_balance": re.compile(r"(?:Average|平均)\s+(?:Balance|結餘)\s*:?\s*(?:HK[D$]\s*)?([0-9,.]+)", re.IGNORECASE),
        "statement_date": re.compile(r"(?:Statement\s+(?:Date|Period)|月結單日期)\s*:?\s*(.+)", re.IGNORECASE),
    },
    "boc": {
        "identifier": re.compile(r"Bank\s+of\s+China|中國銀行|BOC", re.IGNORECASE),
        "account_holder": re.compile(r"(?:Account\s+Holder|戶口持有人)\s*:?\s*(.+)", re.IGNORECASE),
        "account_number": re.compile(r"(?:Account\s+(?:No|Number)|戶口號碼)\s*:?\s*([\d-]+)", re.IGNORECASE),
        "ending_balance": re.compile(r"(?:Ending|Closing|結餘)\s*(?:Balance)?\s*:?\s*(?:HK[D$]\s*)?([0-9,.]+)", re.IGNORECASE),
        "average_balance": re.compile(r"(?:Average|平均)\s*(?:Balance|結餘)\s*:?\s*(?:HK[D$]\s*)?([0-9,.]+)", re.IGNORECASE),
        "statement_date": re.compile(r"(?:Statement\s+(?:Date|Period)|結單日期)\s*:?\s*(.+)", re.IGNORECASE),
    },
    "scb": {
        "identifier": re.compile(r"Standard\s+Chartered|渣打", re.IGNORECASE),
        "account_holder": re.compile(r"(?:Account\s+Holder|Name)\s*:?\s*(.+)", re.IGNORECASE),
        "account_number": re.compile(r"(?:Account\s+(?:No|Number))\s*:?\s*([\d-]+)", re.IGNORECASE),
        "ending_balance": re.compile(r"(?:Ending|Closing)\s+Balance\s*:?\s*(?:HK[D$]\s*)?([0-9,.]+)", re.IGNORECASE),
        "average_balance": re.compile(r"(?:Average|Avg)\s+Balance\s*:?\s*(?:HK[D$]\s*)?([0-9,.]+)", re.IGNORECASE),
        "statement_date": re.compile(r"(?:Statement\s+(?:Date|Period))\s*:?\s*(.+)", re.IGNORECASE),
    },
}

GENERIC_PATTERNS = BANK_PATTERNS["hsbc"]


def _detect_bank(raw_text: str) -> str:
    """Auto-detect bank from raw OCR text."""
    for bank_key, patterns in BANK_PATTERNS.items():
        if patterns["identifier"].search(raw_text):
            return bank_key
    return "unknown"


def _clean_amount(raw: str) -> str:
    """Normalise a currency amount string."""
    return raw.replace(",", "").strip()


def parse_bank_statement(ocr_result: dict[str, Any], bank: str = "auto") -> dict[str, Any]:
    """Parse a bank statement OCR result.

    Returns dict with: bank, account_holder, account_number, ending_balance,
    average_balance, statement_date, field_confidences.
    """
    lines = ocr_result.get("lines", [])
    raw = ocr_result.get("raw_text", "")

    if bank == "auto":
        bank = _detect_bank(raw)

    patterns = BANK_PATTERNS.get(bank, GENERIC_PATTERNS)

    result: dict[str, Any] = {
        "bank": bank,
        "account_holder": None,
        "account_number": None,
        "ending_balance": None,
        "average_balance": None,
        "statement_date": None,
        "field_confidences": {},
    }

    field_keys = ["account_holder", "account_number", "ending_balance", "average_balance", "statement_date"]

    for line in lines:
        text = line.get("text", "").strip()
        conf = line.get("confidence", 0.0)

        for key in field_keys:
            if result[key] is not None:
                continue
            pat = patterns.get(key)
            if not pat:
                continue
            m = pat.search(text)
            if m:
                value = m.group(1).strip()
                if key in ("ending_balance", "average_balance"):
                    value = _clean_amount(value)
                result[key] = value
                result["field_confidences"][key] = conf

    return result
