"""Filing checklist builder per form type."""

from __future__ import annotations

from typing import Any


CHECKLISTS: dict[str, list[dict[str, Any]]] = {
    "BIR51": [
        {"label": "Audited financial statements", "category": "financials", "done": False},
        {"label": "Tax computation schedule", "category": "computation", "done": False},
        {"label": "Supporting schedules (depreciation, provisions, etc.)", "category": "schedules", "done": False},
        {"label": "Director's report and approval", "category": "approval", "done": False},
        {"label": "Profits tax return (BIR51) completed", "category": "form", "done": False},
        {"label": "Section 15E / offshore income claim (if applicable)", "category": "claims", "done": False},
        {"label": "Related party transaction disclosure", "category": "disclosure", "done": False},
        {"label": "Transfer pricing documentation (if applicable)", "category": "disclosure", "done": False},
    ],
    "BIR52": [
        {"label": "Profit & loss account", "category": "financials", "done": False},
        {"label": "Balance sheet", "category": "financials", "done": False},
        {"label": "Tax computation schedule", "category": "computation", "done": False},
        {"label": "Supporting schedules", "category": "schedules", "done": False},
        {"label": "Profits tax return (BIR52) completed", "category": "form", "done": False},
        {"label": "Proprietor / partner approval", "category": "approval", "done": False},
    ],
    "BIR56A": [
        {"label": "IR56B forms for all employees", "category": "employee_forms", "done": False},
        {"label": "IR56E forms for new hires during the year", "category": "employee_forms", "done": False},
        {"label": "IR56F forms for departures during the year", "category": "employee_forms", "done": False},
        {"label": "Employee remuneration summary reconciled", "category": "reconciliation", "done": False},
        {"label": "BIR56A employer's return completed", "category": "form", "done": False},
        {"label": "Director / partner sign-off", "category": "approval", "done": False},
    ],
    "MPF": [
        {"label": "Monthly contribution records prepared", "category": "records", "done": False},
        {"label": "Employee list changes reviewed (new hires / departures)", "category": "changes", "done": False},
        {"label": "Contribution amounts reconciled with payroll", "category": "reconciliation", "done": False},
        {"label": "Payment submitted to MPF trustee", "category": "payment", "done": False},
    ],
    "BR": [
        {"label": "Check current BR certificate expiry date", "category": "preparation", "done": False},
        {"label": "Confirm renewal period (1-year or 3-year)", "category": "preparation", "done": False},
        {"label": "Payment prepared (online / in person)", "category": "payment", "done": False},
        {"label": "Updated BR certificate received and filed", "category": "completion", "done": False},
    ],
}


def generate_checklist(deadline: dict) -> dict[str, Any]:
    """Generate a filing checklist based on the deadline's form code.

    Returns:
        {
            "form_code": "BIR51",
            "total_items": 8,
            "completed_items": 0,
            "items": [{"label": "...", "category": "...", "done": false}, ...]
        }
    """
    form_code = deadline.get("form_code", "")
    deadline_type = deadline.get("deadline_type", "")

    items = _get_items(form_code, deadline_type)

    return {
        "form_code": form_code,
        "deadline_type": deadline_type,
        "total_items": len(items),
        "completed_items": 0,
        "items": items,
    }


def _get_items(form_code: str, deadline_type: str) -> list[dict[str, Any]]:
    """Look up checklist items, falling back by deadline type if form code is not found."""
    if form_code in CHECKLISTS:
        return [item.copy() for item in CHECKLISTS[form_code]]

    type_to_form = {
        "profits_tax": "BIR51",
        "employers_return": "BIR56A",
        "mpf_contribution": "MPF",
        "business_registration": "BR",
    }
    fallback_code = type_to_form.get(deadline_type, "")
    if fallback_code in CHECKLISTS:
        return [item.copy() for item in CHECKLISTS[fallback_code]]

    return [
        {"label": "Prepare required documents", "category": "general", "done": False},
        {"label": "Review and verify information", "category": "general", "done": False},
        {"label": "Submit filing", "category": "general", "done": False},
        {"label": "Confirm receipt / acknowledgment", "category": "general", "done": False},
    ]


def completion_percentage(checklist: dict) -> float:
    """Calculate completion percentage for a checklist."""
    total = checklist.get("total_items", 0)
    if total == 0:
        return 0.0
    completed = checklist.get("completed_items", 0)
    return round(completed / total * 100, 1)
