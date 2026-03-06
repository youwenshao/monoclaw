"""Employment Ordinance (Cap 57) compliance checker for employment contracts."""

from __future__ import annotations

import re
from typing import Any

CAP57_PROVISIONS: list[dict[str, Any]] = [
    {
        "section": "31D",
        "name": "Statutory holidays",
        "description": "Entitlement to 17 statutory holidays per year",
        "keywords": [
            "statutory holiday", "general holiday", "public holiday",
            "17 days", "seventeen days",
        ],
        "compliance_check": "_check_statutory_holidays",
    },
    {
        "section": "31R",
        "name": "Severance payment",
        "description": "Severance payment upon redundancy (2/3 of last month's wages per year of service)",
        "keywords": [
            "severance payment", "severance", "redundancy payment",
            "section 31r",
        ],
        "compliance_check": "_check_severance",
    },
    {
        "section": "31RA",
        "name": "Long service payment",
        "description": "Long service payment for employees with 5+ years of service",
        "keywords": [
            "long service payment", "long service", "section 31ra",
        ],
        "compliance_check": "_check_long_service",
    },
    {
        "section": "10",
        "name": "Wage period",
        "description": "Wage period must not exceed one month; wages due within 7 days",
        "keywords": [
            "wage period", "payment of wages", "salary period", "wages",
            "payable", "monthly",
        ],
        "compliance_check": "_check_wage_period",
    },
    {
        "section": "11A",
        "name": "Annual leave",
        "description": "Paid annual leave entitlement (7-14 days based on service length)",
        "keywords": [
            "annual leave", "paid leave", "vacation", "holiday entitlement",
            "rest day",
        ],
        "compliance_check": "_check_annual_leave",
    },
]


def _find_relevant_clauses(clauses: list[dict[str, Any]], keywords: list[str]) -> list[dict[str, Any]]:
    """Find clauses whose text matches any of the given keywords."""
    matched = []
    for clause in clauses:
        text_lower = clause.get("text_content", "").lower()
        if any(kw.lower() in text_lower for kw in keywords):
            matched.append(clause)
    return matched


def _check_statutory_holidays(matched_clauses: list[dict[str, Any]]) -> dict[str, Any]:
    """Verify statutory holiday provision meets Cap 57 s.31D (17 days)."""
    if not matched_clauses:
        return {"status": "missing", "detail": "No statutory holiday clause found"}

    combined_text = " ".join(c.get("text_content", "") for c in matched_clauses).lower()

    day_match = re.search(r"(\d+)\s*(?:statutory|general|public)\s*holidays?", combined_text)
    if not day_match:
        day_match = re.search(r"(\d+)\s*days?\s*(?:of)?\s*(?:statutory|general|public)", combined_text)

    if day_match:
        days = int(day_match.group(1))
        if days >= 17:
            return {
                "status": "compliant",
                "detail": f"Provides {days} statutory holidays (minimum 17 required)",
            }
        return {
            "status": "non_compliant",
            "detail": f"Only {days} statutory holidays specified; Cap 57 requires 17",
        }

    if "17" in combined_text or "seventeen" in combined_text:
        return {"status": "compliant", "detail": "References 17 statutory holidays"}

    return {
        "status": "present_unverified",
        "detail": "Statutory holiday clause present but specific day count not detected",
    }


def _check_severance(matched_clauses: list[dict[str, Any]]) -> dict[str, Any]:
    """Verify severance payment provision meets Cap 57 s.31R."""
    if not matched_clauses:
        return {"status": "missing", "detail": "No severance payment clause found"}

    combined_text = " ".join(c.get("text_content", "") for c in matched_clauses).lower()

    has_formula = any(
        term in combined_text
        for term in ["2/3", "two-thirds", "two thirds", "per year of service"]
    )

    if has_formula:
        return {
            "status": "compliant",
            "detail": "Severance formula references statutory calculation basis",
        }

    has_waiver = any(
        term in combined_text
        for term in ["waive", "forfeit", "exclude severance", "no severance"]
    )
    if has_waiver:
        return {
            "status": "non_compliant",
            "detail": "Clause appears to waive or exclude statutory severance entitlement",
        }

    return {
        "status": "present_unverified",
        "detail": "Severance clause present but formula compliance not verifiable",
    }


def _check_long_service(matched_clauses: list[dict[str, Any]]) -> dict[str, Any]:
    """Verify long service payment provision meets Cap 57 s.31RA."""
    if not matched_clauses:
        return {"status": "missing", "detail": "No long service payment clause found"}

    combined_text = " ".join(c.get("text_content", "") for c in matched_clauses).lower()

    has_qualifying_period = any(
        term in combined_text
        for term in ["5 years", "five years", "not less than 5"]
    )

    if has_qualifying_period:
        return {
            "status": "compliant",
            "detail": "Long service payment clause references 5-year qualifying period",
        }

    has_exclusion = any(
        term in combined_text
        for term in ["exclude long service", "no long service", "waive"]
    )
    if has_exclusion:
        return {
            "status": "non_compliant",
            "detail": "Clause appears to exclude statutory long service payment",
        }

    return {
        "status": "present_unverified",
        "detail": "Long service payment clause present but qualifying terms not fully verified",
    }


def _check_wage_period(matched_clauses: list[dict[str, Any]]) -> dict[str, Any]:
    """Verify wage period provision meets Cap 57 s.10."""
    if not matched_clauses:
        return {"status": "missing", "detail": "No wage period clause found"}

    combined_text = " ".join(c.get("text_content", "") for c in matched_clauses).lower()

    has_monthly = "monthly" in combined_text or "one month" in combined_text
    has_within_7 = any(
        term in combined_text
        for term in ["within 7 days", "within seven days", "7 days after"]
    )

    if has_monthly and has_within_7:
        return {
            "status": "compliant",
            "detail": "Wage period is monthly with payment within 7 days of period end",
        }

    period_match = re.search(r"(\d+)\s*(?:day|week|month)s?\s*(?:wage|salary|pay)\s*period", combined_text)
    if not period_match:
        period_match = re.search(r"(?:wage|salary|pay)\s*period\s*(?:of|is)?\s*(\d+)\s*(?:day|week|month)", combined_text)

    if period_match:
        return {
            "status": "present_unverified",
            "detail": "Wage period clause present; verify period does not exceed one month",
        }

    if has_monthly:
        return {
            "status": "compliant",
            "detail": "Monthly wage period identified (does not exceed one month)",
        }

    return {
        "status": "present_unverified",
        "detail": "Wage-related clause present but period length not clearly specified",
    }


def _check_annual_leave(matched_clauses: list[dict[str, Any]]) -> dict[str, Any]:
    """Verify annual leave provision meets Cap 57 s.11A (7-14 days)."""
    if not matched_clauses:
        return {"status": "missing", "detail": "No annual leave clause found"}

    combined_text = " ".join(c.get("text_content", "") for c in matched_clauses).lower()

    day_match = re.search(r"(\d+)\s*(?:working\s+)?days?\s*(?:of\s+)?(?:annual|paid)\s*leave", combined_text)
    if not day_match:
        day_match = re.search(r"(?:annual|paid)\s*leave\s*(?:of|is)?\s*(\d+)\s*(?:working\s+)?days?", combined_text)

    if day_match:
        days = int(day_match.group(1))
        if days >= 7:
            return {
                "status": "compliant",
                "detail": f"Provides {days} days annual leave (minimum 7 required after 1 year)",
            }
        return {
            "status": "non_compliant",
            "detail": f"Only {days} days annual leave specified; Cap 57 requires minimum 7 days",
        }

    return {
        "status": "present_unverified",
        "detail": "Annual leave clause present but specific entitlement not clearly stated",
    }


_CHECKERS = {
    "31D": _check_statutory_holidays,
    "31R": _check_severance,
    "31RA": _check_long_service,
    "10": _check_wage_period,
    "11A": _check_annual_leave,
}


def check_cap57_compliance(clauses: list[dict[str, Any]]) -> dict[str, Any]:
    """Validate an employment contract against Cap 57 mandatory provisions.

    Returns a dict with:
        compliant: bool (all provisions present and compliant)
        provisions: list of per-section check results
        summary: human-readable summary
    """
    provisions: list[dict[str, Any]] = []
    all_compliant = True

    for provision in CAP57_PROVISIONS:
        section = provision["section"]
        matched = _find_relevant_clauses(clauses, provision["keywords"])
        checker = _CHECKERS[section]
        result = checker(matched)

        entry = {
            "section": section,
            "name": provision["name"],
            "description": provision["description"],
            "status": result["status"],
            "detail": result["detail"],
            "matched_clauses": [c.get("clause_number", "?") for c in matched],
        }
        provisions.append(entry)

        if result["status"] in ("missing", "non_compliant"):
            all_compliant = False

    missing = [p for p in provisions if p["status"] == "missing"]
    non_compliant = [p for p in provisions if p["status"] == "non_compliant"]
    compliant_count = sum(1 for p in provisions if p["status"] == "compliant")

    summary_parts = [f"{compliant_count}/{len(provisions)} provisions verified compliant"]
    if missing:
        summary_parts.append(
            f"{len(missing)} missing: {', '.join(f's.{p['section']}' for p in missing)}"
        )
    if non_compliant:
        summary_parts.append(
            f"{len(non_compliant)} non-compliant: {', '.join(f's.{p['section']}' for p in non_compliant)}"
        )

    return {
        "compliant": all_compliant,
        "provisions": provisions,
        "summary": "; ".join(summary_parts),
    }
