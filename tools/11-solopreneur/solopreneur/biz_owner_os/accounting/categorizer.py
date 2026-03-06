"""LLM-powered expense categorizer with keyword fallback."""

from __future__ import annotations

from typing import Any

CATEGORIES = [
    "rent",
    "salary",
    "inventory",
    "utilities",
    "marketing",
    "equipment",
    "mpf",
    "insurance",
    "other",
]

_KEYWORD_MAP: dict[str, str] = {
    "rent": "rent",
    "租金": "rent",
    "lease": "rent",
    "salary": "salary",
    "wage": "salary",
    "薪金": "salary",
    "payroll": "salary",
    "inventory": "inventory",
    "stock": "inventory",
    "存貨": "inventory",
    "supplier": "inventory",
    "electricity": "utilities",
    "water": "utilities",
    "gas": "utilities",
    "internet": "utilities",
    "電費": "utilities",
    "水費": "utilities",
    "marketing": "marketing",
    "ads": "marketing",
    "advertising": "marketing",
    "廣告": "marketing",
    "facebook ads": "marketing",
    "google ads": "marketing",
    "equipment": "equipment",
    "machine": "equipment",
    "設備": "equipment",
    "repair": "equipment",
    "maintenance": "equipment",
    "mpf": "mpf",
    "強積金": "mpf",
    "pension": "mpf",
    "insurance": "insurance",
    "保險": "insurance",
}

_LLM_PROMPT = (
    "You are an expense categorizer for a Hong Kong small business. "
    "Given the expense description below, respond with ONLY one of these "
    "category codes: {categories}.\n\n"
    "Description: {description}\n\n"
    "Category:"
)


def _keyword_match(description: str) -> str | None:
    """Try to match the description against known keywords."""
    lower = description.lower()
    for keyword, category in _KEYWORD_MAP.items():
        if keyword.lower() in lower:
            return category
    return None


async def categorize_expense(description: str, llm: Any = None) -> str:
    """Return a category string for the given expense description.

    Tries keyword matching first for speed, then falls back to LLM.
    """
    matched = _keyword_match(description)
    if matched:
        return matched

    if llm is not None:
        try:
            prompt = _LLM_PROMPT.format(
                categories=", ".join(CATEGORIES),
                description=description,
            )
            result = await llm.generate(prompt)
            category = result.strip().lower() if isinstance(result, str) else str(result).strip().lower()
            if category in CATEGORIES:
                return category
        except Exception:
            pass

    return "other"
