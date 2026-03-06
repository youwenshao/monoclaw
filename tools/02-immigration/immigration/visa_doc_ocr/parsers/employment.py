"""Employment contract parser."""

from __future__ import annotations

import re
from typing import Any


def _clean_salary(raw: str) -> str:
    return raw.replace(",", "").replace("$", "").replace("HKD", "").replace("HK", "").strip()


def parse_employment_contract(ocr_result: dict[str, Any]) -> dict[str, Any]:
    """Parse an employment contract OCR result.

    Returns dict with: employer_name, position, salary, start_date,
    contract_duration, field_confidences.
    """
    lines = ocr_result.get("lines", [])

    result: dict[str, Any] = {
        "employer_name": None,
        "position": None,
        "salary": None,
        "start_date": None,
        "contract_duration": None,
        "field_confidences": {},
    }

    patterns = {
        "employer_name": re.compile(
            r"(?:Employer|Company|僱主|公司)\s*:?\s*(.+)", re.IGNORECASE
        ),
        "position": re.compile(
            r"(?:Position|Title|Job\s+Title|職位)\s*:?\s*(.+)", re.IGNORECASE
        ),
        "salary": re.compile(
            r"(?:Monthly\s+)?(?:Salary|Remuneration|薪金|月薪)\s*:?\s*(?:HK[D$]\s*)?([0-9,.]+)",
            re.IGNORECASE,
        ),
        "start_date": re.compile(
            r"(?:Start\s+Date|Commencement|開始日期)\s*:?\s*(\d{1,2}\s*[A-Za-z]+\s*\d{4}|\d{2}/\d{2}/\d{4}|\d{4}-\d{2}-\d{2})",
            re.IGNORECASE,
        ),
        "contract_duration": re.compile(
            r"(?:Duration|Period|Term|合約期)\s*:?\s*(\d+\s*(?:year|month|yr|mo|年|月)s?)",
            re.IGNORECASE,
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
                if key == "salary":
                    value = _clean_salary(value)
                result[key] = value
                result["field_confidences"][key] = conf

    return result
