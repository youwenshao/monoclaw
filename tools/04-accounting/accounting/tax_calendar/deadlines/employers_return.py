"""HK Employer's Return (BIR56A) deadline rules."""

from __future__ import annotations

from datetime import date
from typing import Any


def calculate_employers_return(
    client: dict, assessment_year: str, config: dict
) -> list[dict]:
    """Calculate BIR56A (Employer's Return) filing deadline.

    Issued by IRD on 1 April each year.
    Must be filed within one month — due by early May.
    No extension is available for employer's returns.
    Accompanying forms: IR56B (per employee), IR56E (new hires), IR56F (departures).
    """
    parts = assessment_year.split("/")
    start_year = int(parts[0])
    end_suffix = parts[1] if len(parts) > 1 else str(start_year + 1)[-2:]
    end_year = int(str(start_year)[:2] + end_suffix)

    issue_date = date(end_year, 4, 1)
    original_due = date(end_year, 5, 2)

    deadline: dict[str, Any] = {
        "client_id": client["id"],
        "deadline_type": "employers_return",
        "form_code": "BIR56A",
        "assessment_year": assessment_year,
        "original_due_date": original_due,
        "extended_due_date": None,
        "extension_type": None,
        "extension_status": None,
        "filing_status": "not_started",
        "notes": f"Issued {issue_date.isoformat()}. No extension available.",
    }
    return [deadline]


def accompanying_forms() -> list[dict[str, str]]:
    """Reference list of forms that accompany BIR56A."""
    return [
        {
            "form": "IR56B",
            "description": "Annual return for each employee earning above HK$132,000 or assessable income.",
        },
        {
            "form": "IR56E",
            "description": "Notification of new employee commencement within 3 months of start date.",
        },
        {
            "form": "IR56F",
            "description": "Notification of employee cessation at least 1 month before departure or leaving date.",
        },
        {
            "form": "IR56G",
            "description": "Notification of employee departing HK for a period exceeding 1 month.",
        },
    ]
