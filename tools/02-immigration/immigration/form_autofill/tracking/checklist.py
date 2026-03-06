"""Document checklist generator — cross-references form requirements with OCR inventory."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from openclaw_shared.database import get_db

logger = logging.getLogger("openclaw.immigration.form_autofill.checklist")

_DOC_TYPE_ALIASES: dict[str, list[str]] = {
    "passport": ["passport", "travel_document"],
    "hkid": ["hkid", "hk_id_card", "id_card"],
    "visa_label": ["visa_label", "visa", "endorsement_label"],
    "photo": ["photo", "photograph", "portrait"],
    "employer_letter": ["employer_letter", "employment_letter", "sponsorship_letter"],
    "employment_contract": ["employment_contract", "contract"],
    "business_registration": ["business_registration", "br_certificate"],
    "academic_certificate": ["academic_certificate", "degree", "diploma", "certificate"],
    "transcript": ["transcript", "academic_transcript"],
    "bank_statement": ["bank_statement", "financial_proof"],
    "reference_letter": ["reference_letter", "work_reference"],
    "tax_return": ["tax_return", "tax_certificate"],
    "birth_certificate": ["birth_certificate"],
    "mainland_id": ["mainland_id", "prc_id", "resident_id"],
}


def generate_checklist(
    scheme: str,
    client_id: int,
    ocr_db_path: str | Path,
) -> dict[str, Any]:
    """Build a checklist for *scheme* and cross-reference with OCR document inventory.

    Returns::

        {
            "items": [
                {"name": str, "required": bool, "submitted": bool, "notes": str},
                ...
            ],
            "completeness_pct": float,
        }
    """
    from immigration.form_autofill.forms.base import get_form_definition

    form_type = _scheme_to_form_type(scheme)
    form_def = get_form_definition(form_type)
    raw_checklist = form_def.get_checklist()

    submitted_types = _get_submitted_doc_types(client_id, ocr_db_path)

    items: list[dict[str, Any]] = []
    required_count = 0
    submitted_count = 0

    for item in raw_checklist:
        is_submitted = _has_matching_document(item["name"], submitted_types)
        items.append({
            "name": item["name"],
            "required": item["required"],
            "submitted": is_submitted,
            "notes": item.get("notes", ""),
        })
        if item["required"]:
            required_count += 1
            if is_submitted:
                submitted_count += 1

    completeness = (submitted_count / required_count * 100) if required_count > 0 else 100.0

    return {
        "items": items,
        "completeness_pct": round(completeness, 1),
    }


def _scheme_to_form_type(scheme: str) -> str:
    """Map a scheme name to the primary form type."""
    mapping: dict[str, str] = {
        "GEP": "GEP",
        "ASMTP": "ASMTP",
        "QMAS": "QMAS",
        "IANG": "IANG",
        "EXTENSION": "ID990A",
        "CHANGE_SPONSORSHIP": "ID990B",
        "ID990A": "ID990A",
        "ID990B": "ID990B",
    }
    return mapping.get(scheme.upper(), scheme.upper())


def _get_submitted_doc_types(client_id: int, ocr_db_path: str | Path) -> set[str]:
    """Query the VisaDoc OCR database for documents already submitted by this client."""
    try:
        with get_db(ocr_db_path) as conn:
            rows = conn.execute(
                "SELECT doc_type FROM documents WHERE client_id = ? AND status = 'processed'",
                (client_id,),
            ).fetchall()
        return {r["doc_type"] for r in rows}
    except Exception:
        logger.warning("Could not query OCR DB for client %d — treating as no docs submitted", client_id)
        return set()


def _has_matching_document(checklist_item_name: str, submitted_types: set[str]) -> bool:
    """Fuzzy-match a checklist item name against submitted document types."""
    name_lower = checklist_item_name.lower()

    for canonical, aliases in _DOC_TYPE_ALIASES.items():
        if any(alias in name_lower for alias in aliases):
            if submitted_types & set(aliases) or canonical in submitted_types:
                return True

    return False
