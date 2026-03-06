"""Hong Kong real-estate domain utilities."""

from __future__ import annotations

import re
from typing import Any

# ---------------------------------------------------------------------------
# MTR proximity grading
# ---------------------------------------------------------------------------

_MTR_GRADES = [
    (5, "A"),   # ≤ 5 min
    (10, "B"),  # ≤ 10 min
    (20, "C"),  # ≤ 20 min
]


def score_mtr_proximity(walk_minutes: int | float | None) -> str:
    """Grade MTR proximity based on walking time.

    A — ≤ 5 min, B — ≤ 10 min, C — ≤ 20 min, D — > 20 min or unknown.
    """
    if walk_minutes is None:
        return "D"
    for threshold, grade in _MTR_GRADES:
        if walk_minutes <= threshold:
            return grade
    return "D"


# ---------------------------------------------------------------------------
# School-net lookup (simplified reference data)
# ---------------------------------------------------------------------------

_SCHOOL_NETS: dict[int, dict[str, Any]] = {
    11: {
        "district": "Central & Western",
        "popular_schools": [
            "St. Joseph's Primary School",
            "嘉諾撒聖心學校",
            "聖士提反女子中學附屬小學",
        ],
    },
    12: {
        "district": "Wan Chai",
        "popular_schools": [
            "瑪利曼小學",
            "聖保祿天主教小學",
            "番禺會所華仁小學",
        ],
    },
    34: {
        "district": "Kowloon City",
        "popular_schools": [
            "喇沙小學",
            "瑪利諾修院學校(小學部)",
            "陳瑞祺(喇沙)小學",
        ],
    },
    35: {
        "district": "Kowloon City (North)",
        "popular_schools": [
            "拔萃小學",
            "協恩中學附屬小學",
        ],
    },
    41: {
        "district": "Kowloon Tong / Beacon Hill",
        "popular_schools": [
            "拔萃男書院附屬小學",
            "華德學校",
        ],
    },
}


def get_school_net_info(net_number: int | None) -> dict[str, Any]:
    """Return school-net info for the given net number.

    Returns a dict with ``district`` and ``popular_schools``, or an
    empty dict if the net is unknown.
    """
    if net_number is None:
        return {}
    return _SCHOOL_NETS.get(net_number, {})


# ---------------------------------------------------------------------------
# Price formatting
# ---------------------------------------------------------------------------

def format_price_hkd(amount: int | float, language: str = "en") -> str:
    """Format a HKD price for display.

    * **en** — HK$12.8M, HK$800K, HK$1,280
    * **zh** — $1,280萬, $80萬, $1,280
    """
    if amount < 0:
        sign = "-"
        amount = abs(amount)
    else:
        sign = ""

    if language == "zh":
        if amount >= 1_0000_0000:
            return f"{sign}${amount / 1_0000_0000:,.2f}億"
        if amount >= 1_0000:
            wan = amount / 1_0000
            formatted = f"{wan:,.1f}".rstrip("0").rstrip(".")
            return f"{sign}${formatted}萬"
        return f"{sign}${amount:,.0f}"

    if amount >= 1_000_000:
        millions = amount / 1_000_000
        formatted = f"{millions:,.1f}".rstrip("0").rstrip(".")
        return f"{sign}HK${formatted}M"
    if amount >= 1_000:
        thousands = amount / 1_000
        formatted = f"{thousands:,.1f}".rstrip("0").rstrip(".")
        return f"{sign}HK${formatted}K"
    return f"{sign}HK${amount:,.0f}"


# ---------------------------------------------------------------------------
# Saleable-area validation
# ---------------------------------------------------------------------------

_SALEABLE_PATTERNS = [
    re.compile(r"saleable\s+area", re.IGNORECASE),
    re.compile(r"實用面積"),
]


def validate_saleable_area(description: str) -> bool:
    """Check whether a listing description references saleable area as the primary metric.

    Under the Residential Properties (First-hand Sales) Ordinance, saleable
    area (實用面積) must be the primary area quoted.
    """
    return any(p.search(description) for p in _SALEABLE_PATTERNS)
