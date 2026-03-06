"""Hong Kong BIR60 tax return parser."""

from __future__ import annotations

import re
from typing import Any


def _clean_amount(raw: str) -> str:
    return raw.replace(",", "").replace("$", "").replace("HKD", "").strip()


def parse_tax_return(ocr_result: dict[str, Any]) -> dict[str, Any]:
    """Parse a BIR60 individual tax return OCR result.

    Returns dict with: total_income, tax_payable, net_chargeable_income,
    tax_year, field_confidences.
    """
    lines = ocr_result.get("lines", [])

    result: dict[str, Any] = {
        "total_income": None,
        "tax_payable": None,
        "net_chargeable_income": None,
        "tax_year": None,
        "field_confidences": {},
    }

    patterns = {
        "total_income": re.compile(
            r"(?:Total\s+Income|入息總額)\s*:?\s*(?:HK[D$]\s*)?([0-9,.]+)", re.IGNORECASE
        ),
        "tax_payable": re.compile(
            r"(?:Tax\s+Payable|應繳稅款)\s*:?\s*(?:HK[D$]\s*)?([0-9,.]+)", re.IGNORECASE
        ),
        "net_chargeable_income": re.compile(
            r"(?:Net\s+Chargeable\s+Income|應課稅入息實額)\s*:?\s*(?:HK[D$]\s*)?([0-9,.]+)", re.IGNORECASE
        ),
        "tax_year": re.compile(
            r"(?:Year\s+of\s+Assessment|課稅年度)\s*:?\s*(\d{4}/\d{2,4})", re.IGNORECASE
        ),
    }

    for line in lines:
        text = line.get("text", "").strip()
        conf = line.get("confidence", 0.0)

        for key, pat in patterns.items():
            if result[key] is not None:
                continue
            m = pat.search(text)
            if m:
                value = m.group(1).strip()
                if key != "tax_year":
                    value = _clean_amount(value)
                result[key] = value
                result["field_confidences"][key] = conf

    return result
