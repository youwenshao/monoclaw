"""Expense auto-categorization for invoice line items.

Categorization priority:
1. Supplier default category (from suppliers table)
2. Category rules (from category_rules table)
3. Keyword-based matching (built-in heuristics)
"""

from __future__ import annotations

import re
from typing import Any

from openclaw_shared.database import get_db

_KEYWORD_CATEGORIES: list[tuple[re.Pattern, str, str]] = [
    (re.compile(r"rent|lease|office\s*space|premises", re.IGNORECASE), "Rent & Premises", "5100"),
    (re.compile(r"electric|water|gas|utilit|internet|broadband|telecom", re.IGNORECASE), "Utilities", "5200"),
    (re.compile(r"salary|wages|payroll|mpf|bonus|staff", re.IGNORECASE), "Staff Costs", "5300"),
    (re.compile(r"consult|advisory|professional\s*fee|legal\s*fee|audit", re.IGNORECASE), "Professional Fees", "5400"),
    (re.compile(r"travel|transport|taxi|uber|flight|hotel|accomm", re.IGNORECASE), "Travel & Transport", "5500"),
    (re.compile(r"meal|food|entertain|dining|restaurant|catering", re.IGNORECASE), "Meals & Entertainment", "5600"),
    (re.compile(r"print|stationer|office\s*suppl|toner|paper", re.IGNORECASE), "Office Supplies", "5700"),
    (re.compile(r"software|licen[cs]e|subscription|saas|cloud", re.IGNORECASE), "Software & IT", "5800"),
    (re.compile(r"insurance|premium|cover", re.IGNORECASE), "Insurance", "5900"),
    (re.compile(r"advertis|marketing|promotion|sponsor|google\s*ads|facebook", re.IGNORECASE), "Marketing", "6000"),
    (re.compile(r"repair|maintenance|cleaning|janitorial", re.IGNORECASE), "Repairs & Maintenance", "6100"),
    (re.compile(r"bank\s*charge|interest|finance\s*charge|service\s*fee", re.IGNORECASE), "Bank Charges", "6200"),
    (re.compile(r"depreci|amortiz", re.IGNORECASE), "Depreciation", "6300"),
    (re.compile(r"courier|shipping|freight|postage|delivery", re.IGNORECASE), "Shipping & Courier", "6400"),
    (re.compile(r"training|education|seminar|workshop|course", re.IGNORECASE), "Training", "6500"),
]


def categorize(
    supplier_name: str | None,
    description: str | None,
    db_path: str,
) -> dict[str, Any]:
    """Determine the expense category for an invoice.

    Returns dict with: category, account_code, confidence, source.
    """
    if supplier_name:
        supplier_result = _lookup_supplier_default(supplier_name, db_path)
        if supplier_result:
            return supplier_result

    combined_text = " ".join(filter(None, [supplier_name, description]))

    if combined_text:
        rule_result = _match_category_rules(combined_text, db_path)
        if rule_result:
            return rule_result

    if combined_text:
        keyword_result = _match_keywords(combined_text)
        if keyword_result:
            return keyword_result

    return {
        "category": "General Expenses",
        "account_code": "5000",
        "confidence": 0.1,
        "source": "default",
    }


def _lookup_supplier_default(supplier_name: str, db_path: str) -> dict[str, Any] | None:
    """Check the suppliers table for a default category."""
    with get_db(db_path) as conn:
        row = conn.execute(
            """SELECT default_category, default_account_code FROM suppliers
               WHERE LOWER(name) = LOWER(?) AND default_category IS NOT NULL
               LIMIT 1""",
            (supplier_name,),
        ).fetchone()

    if row and row[0]:
        return {
            "category": row[0],
            "account_code": row[1] or "5000",
            "confidence": 0.95,
            "source": "supplier_default",
        }
    return None


def _match_category_rules(text: str, db_path: str) -> dict[str, Any] | None:
    """Match against user-defined category rules in the database."""
    with get_db(db_path) as conn:
        rules = conn.execute(
            "SELECT match_type, match_value, category, account_code, confidence FROM category_rules"
        ).fetchall()

    for rule in rules:
        match_type, match_value, category, account_code, confidence = rule
        matched = False

        if match_type == "exact" and text.lower() == match_value.lower():
            matched = True
        elif match_type == "contains" and match_value.lower() in text.lower():
            matched = True
        elif match_type == "regex":
            try:
                if re.search(match_value, text, re.IGNORECASE):
                    matched = True
            except re.error:
                continue

        if matched:
            return {
                "category": category,
                "account_code": account_code or "5000",
                "confidence": float(confidence) if confidence else 0.8,
                "source": "category_rule",
            }

    return None


def _match_keywords(text: str) -> dict[str, Any] | None:
    """Match against built-in keyword patterns."""
    for pattern, category, account_code in _KEYWORD_CATEGORIES:
        if pattern.search(text):
            return {
                "category": category,
                "account_code": account_code,
                "confidence": 0.6,
                "source": "keyword_match",
            }
    return None
