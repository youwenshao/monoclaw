"""Document expiry and freshness validator."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

FRESHNESS_RULES: dict[str, timedelta] = {
    "bank_statement": timedelta(days=90),
    "tax_return": timedelta(days=365),
    "salary_proof": timedelta(days=90),
    "employment_proof": timedelta(days=180),
}


def _parse_date(raw: str | None) -> date | None:
    """Try several date formats and return a date or None."""
    if not raw:
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d %b %Y", "%d %B %Y"):
        try:
            return datetime.strptime(raw.strip(), fmt).date()
        except (ValueError, TypeError):
            continue
    return None


def check_document_expiry(documents: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Flag documents that are expired or too old.

    Rules:
    - Bank statements older than 3 months are stale.
    - Tax returns older than 1 year are stale.
    - Passports past their expiry_date are expired.
    - Documents with expiry_date < today are expired.

    Returns a list of flag dicts, each with: doc_id, doc_type, flag_type, message.
    """
    today = date.today()
    flags: list[dict[str, Any]] = []

    for doc in documents:
        doc_id = doc.get("id")
        doc_type = doc.get("doc_type", "unknown")

        expiry_raw = doc.get("expiry_date")
        expiry = _parse_date(expiry_raw)
        if expiry and expiry < today:
            flags.append({
                "doc_id": doc_id,
                "doc_type": doc_type,
                "flag_type": "expired",
                "message": f"{doc_type} expired on {expiry.isoformat()}",
            })

        max_age = FRESHNESS_RULES.get(doc_type)
        if max_age:
            created_raw = doc.get("issue_date") or doc.get("created_at") or doc.get("processed_at")
            created = _parse_date(str(created_raw) if created_raw else None)
            if created and (today - created) > max_age:
                age_days = (today - created).days
                limit_days = max_age.days
                flags.append({
                    "doc_id": doc_id,
                    "doc_type": doc_type,
                    "flag_type": "stale",
                    "message": f"{doc_type} is {age_days} days old (limit: {limit_days} days)",
                })

        if doc_type == "passport":
            six_months = today + timedelta(days=180)
            if expiry and expiry < six_months and expiry >= today:
                flags.append({
                    "doc_id": doc_id,
                    "doc_type": doc_type,
                    "flag_type": "expiring_soon",
                    "message": f"Passport expires on {expiry.isoformat()} (within 6 months)",
                })

    return flags
