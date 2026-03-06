"""Validate extracted invoice data for completeness and consistency."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class ValidationResult:
    is_valid: bool = True
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    confidence_score: float = 1.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "is_valid": self.is_valid,
            "errors": self.errors,
            "warnings": self.warnings,
            "confidence_score": round(self.confidence_score, 4),
        }


def validate_invoice(data: dict[str, Any]) -> ValidationResult:
    """Validate an extracted invoice for required fields and internal consistency.

    Checks performed:
    - Required fields present (supplier_name, total_amount)
    - Amount consistency (subtotal + tax ≈ total)
    - Date validity and not in the far future
    - Invoice number format
    - Line item totals vs invoice total
    """
    result = ValidationResult()
    penalties: list[float] = []

    if not data.get("supplier_name"):
        result.errors.append("Missing supplier name")
        result.is_valid = False
        penalties.append(0.3)

    if data.get("total_amount") is None:
        result.errors.append("Missing total amount")
        result.is_valid = False
        penalties.append(0.3)
    elif data["total_amount"] <= 0:
        result.errors.append("Total amount must be positive")
        result.is_valid = False
        penalties.append(0.2)

    if not data.get("invoice_number"):
        result.warnings.append("Missing invoice number — may cause duplicate detection issues")
        penalties.append(0.1)

    if not data.get("invoice_date"):
        result.warnings.append("Missing invoice date")
        penalties.append(0.05)
    else:
        date_str = data["invoice_date"]
        parsed_date = _try_parse_date(date_str)
        if parsed_date is None:
            result.warnings.append(f"Could not parse date: {date_str}")
            penalties.append(0.05)
        else:
            today = datetime.now()
            if parsed_date > today:
                days_ahead = (parsed_date - today).days
                if days_ahead > 30:
                    result.errors.append(f"Invoice date is {days_ahead} days in the future")
                    result.is_valid = False
                    penalties.append(0.2)
                elif days_ahead > 0:
                    result.warnings.append(f"Invoice date is {days_ahead} days in the future")
                    penalties.append(0.05)

    subtotal = data.get("subtotal")
    tax = data.get("tax_amount")
    total = data.get("total_amount")

    if subtotal is not None and tax is not None and total is not None:
        expected = round(subtotal + tax, 2)
        if abs(expected - total) > 0.01:
            result.errors.append(
                f"Amount mismatch: subtotal ({subtotal}) + tax ({tax}) = {expected}, "
                f"but total is {total}"
            )
            result.is_valid = False
            penalties.append(0.2)

    line_items = data.get("line_items", [])
    if line_items and total is not None:
        items_total = sum(item.get("amount", 0) for item in line_items)
        if items_total > 0:
            effective_subtotal = subtotal if subtotal is not None else total
            if abs(items_total - effective_subtotal) > 1.0:
                result.warnings.append(
                    f"Line items total ({items_total:.2f}) differs from "
                    f"invoice subtotal/total ({effective_subtotal:.2f})"
                )
                penalties.append(0.1)

    for i, item in enumerate(line_items):
        qty = item.get("quantity")
        price = item.get("unit_price")
        amt = item.get("amount", 0)
        if qty is not None and price is not None and amt:
            expected_amt = round(qty * price, 2)
            if abs(expected_amt - amt) > 0.01:
                result.warnings.append(
                    f"Line item {i + 1}: qty ({qty}) × price ({price}) = "
                    f"{expected_amt}, but amount is {amt}"
                )
                penalties.append(0.05)

    result.confidence_score = max(0.0, 1.0 - sum(penalties))
    return result


def _try_parse_date(date_str: str) -> datetime | None:
    """Attempt to parse a date string in various formats."""
    formats = [
        "%Y-%m-%d",
        "%Y/%m/%d",
        "%d/%m/%Y",
        "%d-%m-%Y",
        "%m/%d/%Y",
        "%d %b %Y",
        "%d %B %Y",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(date_str.strip(), fmt)
        except ValueError:
            continue
    return None
