"""Cross-form field validation engine."""

from __future__ import annotations

import re
from typing import Any


def validate_fields(form_type: str, field_values: dict[str, Any]) -> dict[str, Any]:
    """Validate *field_values* against the schema for *form_type*.

    Returns::

        {
            "valid": bool,
            "errors":   [{"field": str, "message": str}, ...],
            "warnings": [{"field": str, "message": str}, ...],
        }
    """
    from immigration.form_autofill.forms.base import get_form_definition

    form_def = get_form_definition(form_type)
    result = form_def.validate(field_values)

    _cross_field_checks(field_values, result)
    result["valid"] = len(result["errors"]) == 0
    return result


def _cross_field_checks(fv: dict[str, Any], result: dict[str, Any]) -> None:
    """Additional checks that apply across all form types."""
    errors = result["errors"]
    warnings = result["warnings"]

    hkid = fv.get("hkid", "")
    if hkid and not _valid_hkid_format(hkid):
        errors.append({
            "field": "hkid",
            "message": "HKID format invalid — expected A123456(7) or AB123456(7)",
        })

    nationality = fv.get("nationality", "")
    if nationality and len(nationality) < 2:
        warnings.append({
            "field": "nationality",
            "message": "Nationality seems too short — use full country name (e.g. BRITISH, CHINESE)",
        })

    for key in ("contact_email", "email"):
        email = fv.get(key, "")
        if email and not _valid_email(email):
            errors.append({
                "field": key,
                "message": "Invalid email address format",
            })

    passport = fv.get("passport_number", "")
    if passport and len(passport) < 5:
        warnings.append({
            "field": "passport_number",
            "message": "Passport number seems too short",
        })


def _valid_hkid_format(hkid: str) -> bool:
    """Check HKID format: 1-2 letters + 6 digits + (check digit)."""
    return bool(re.match(r"^[A-Z]{1,2}\d{6}\(\d\)$", hkid.upper()))


def _valid_email(email: str) -> bool:
    return bool(re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email))
