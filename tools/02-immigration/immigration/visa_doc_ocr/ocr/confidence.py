"""Confidence scoring for OCR results."""

from __future__ import annotations

from typing import Any

FIELD_WEIGHTS: dict[str, float] = {
    "name_en": 2.0,
    "name_zh": 1.5,
    "hkid_number": 2.5,
    "passport_number": 2.5,
    "date_of_birth": 2.0,
    "nationality": 1.0,
    "issue_date": 1.0,
    "expiry_date": 1.5,
    "account_number": 2.0,
    "account_holder": 1.5,
    "ending_balance": 2.0,
    "average_balance": 1.5,
    "total_income": 2.0,
    "tax_payable": 1.5,
    "employer_name": 1.5,
    "salary": 2.0,
    "position": 1.0,
}

DEFAULT_WEIGHT = 1.0


def score_fields(ocr_result: dict[str, Any]) -> float:
    """Compute an overall confidence score from per-line OCR confidences.

    Uses a weighted average where document-critical fields carry more weight.
    Returns a value between 0.0 and 1.0.
    """
    lines = ocr_result.get("lines", [])
    if not lines:
        return 0.0

    total_weight = 0.0
    weighted_sum = 0.0

    for line in lines:
        conf = line.get("confidence", 0.0)
        text = line.get("text", "").lower()

        weight = DEFAULT_WEIGHT
        for field_key, field_weight in FIELD_WEIGHTS.items():
            keywords = field_key.replace("_", " ").split()
            if any(kw in text for kw in keywords):
                weight = max(weight, field_weight)
                break

        weighted_sum += conf * weight
        total_weight += weight

    if total_weight == 0:
        return 0.0

    return round(min(max(weighted_sum / total_weight, 0.0), 1.0), 4)
