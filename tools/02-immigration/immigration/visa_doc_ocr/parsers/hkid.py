"""HKID card parser and validator."""

from __future__ import annotations

import re
from typing import Any


def validate_hkid(hkid: str) -> bool:
    """Validate an HKID number using the official check-digit algorithm.

    Format: 1-2 uppercase letters + 6 digits + check digit in parentheses.
    Algorithm: assign A=10..Z=35, multiply each position by weight [9,8,7,...,1],
    sum mod 11 — remainder 0 means check digit '0', remainder 1 means 'A'.
    """
    if not hkid:
        return False
    hkid = hkid.strip().upper()
    m = re.match(r"^([A-Z]{1,2})(\d{6})\(([0-9A])\)$", hkid)
    if not m:
        return False

    prefix, digits, check_char = m.group(1), m.group(2), m.group(3)

    values: list[int] = []
    if len(prefix) == 1:
        values.append(36)  # space placeholder weighted at position 9
        values.append(ord(prefix) - 55)
    else:
        values.append(ord(prefix[0]) - 55)
        values.append(ord(prefix[1]) - 55)

    for d in digits:
        values.append(int(d))

    weights = list(range(9, 1, -1))  # [9, 8, 7, 6, 5, 4, 3, 2]
    if len(values) != len(weights):
        return False

    total = sum(v * w for v, w in zip(values, weights))
    remainder = total % 11

    if remainder == 0:
        expected = "0"
    elif remainder == 1:
        expected = "A"
    else:
        expected = str(11 - remainder)

    return check_char == expected


def parse_hkid(ocr_result: dict[str, Any]) -> dict[str, Any]:
    """Extract structured fields from HKID OCR output.

    Returns dict with: name_en, name_zh, hkid_number, date_of_birth, issue_date,
    valid (bool from check digit), and field_confidences.
    """
    lines = ocr_result.get("lines", [])
    raw = ocr_result.get("raw_text", "")

    result: dict[str, Any] = {
        "name_en": None,
        "name_zh": None,
        "hkid_number": None,
        "date_of_birth": None,
        "issue_date": None,
        "valid": False,
        "field_confidences": {},
    }

    hkid_pattern = re.compile(r"[A-Z]{1,2}\d{6}\([0-9A]\)")
    date_pattern = re.compile(r"\d{2}-\d{2}-\d{4}")
    cjk_pattern = re.compile(r"[\u4e00-\u9fff\u3400-\u4dbf]+")
    name_en_pattern = re.compile(r"^([A-Z][A-Za-z]+),?\s+([A-Z][A-Za-z\s]+)$")

    dates_found: list[tuple[str, float]] = []

    for line in lines:
        text = line.get("text", "").strip()
        conf = line.get("confidence", 0.0)

        hkid_match = hkid_pattern.search(text)
        if hkid_match and not result["hkid_number"]:
            result["hkid_number"] = hkid_match.group()
            result["valid"] = validate_hkid(result["hkid_number"])
            result["field_confidences"]["hkid_number"] = conf
            continue

        date_match = date_pattern.search(text)
        if date_match:
            dates_found.append((date_match.group(), conf))
            continue

        if not result["name_zh"] and cjk_pattern.search(text):
            cleaned = cjk_pattern.search(text)
            if cleaned and len(cleaned.group()) >= 2:
                upper = text.upper()
                if "身份證" not in text and "居民" not in text and "香港" not in upper:
                    result["name_zh"] = cleaned.group()
                    result["field_confidences"]["name_zh"] = conf
                    continue

        en_match = name_en_pattern.match(text)
        if en_match and not result["name_en"]:
            upper = text.upper()
            skip_keywords = {"HONG", "KONG", "IDENTITY", "CARD", "PERMANENT", "RESIDENT"}
            if not any(kw in upper for kw in skip_keywords):
                result["name_en"] = text
                result["field_confidences"]["name_en"] = conf

    if len(dates_found) >= 1:
        result["date_of_birth"] = dates_found[0][0]
        result["field_confidences"]["date_of_birth"] = dates_found[0][1]
    if len(dates_found) >= 2:
        result["issue_date"] = dates_found[1][0]
        result["field_confidences"]["issue_date"] = dates_found[1][1]

    return result
