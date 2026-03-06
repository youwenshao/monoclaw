"""Map client database records to form field values."""

from __future__ import annotations

from datetime import datetime
from typing import Any


def map_client_to_fields(client: dict[str, Any], form_type: str) -> dict[str, Any]:
    """Map a client DB row to a dict of form field values for *form_type*.

    Applies BLOCK CAPITALS transformation for English text fields and
    converts dates from ISO 8601 (YYYY-MM-DD) to DD/MM/YYYY.
    """
    from immigration.form_autofill.forms.base import get_form_definition

    form_def = get_form_definition(form_type)
    field_defs = {f["name"]: f for f in form_def.get_field_list()}

    mapping = _build_mapping(form_type)
    result: dict[str, Any] = {}

    for form_field, client_keys in mapping.items():
        if form_field not in field_defs:
            continue

        value = None
        for ck in client_keys:
            value = client.get(ck)
            if value is not None and value != "":
                break

        if value is None:
            continue

        fdef = field_defs[form_field]
        result[form_field] = _transform(value, fdef)

    return result


def _build_mapping(form_type: str) -> dict[str, list[str]]:
    """Return {form_field_name: [client_db_column, ...]} for the given form.

    Multiple client columns allow fallbacks (e.g. ``surname_en`` might live
    in the dedicated column or be parsed from ``name_en``).
    """
    common: dict[str, list[str]] = {
        "surname_en": ["surname_en"],
        "given_name_en": ["given_name_en"],
        "name_zh": ["name_zh"],
        "sex": ["gender"],
        "date_of_birth": ["date_of_birth"],
        "nationality": ["nationality"],
        "passport_number": ["passport_number"],
        "passport_expiry_date": ["passport_expiry"],
        "hkid": ["hkid"],
        "contact_phone": ["phone"],
        "contact_email": ["email"],
        "residential_address": ["address_hk"],
        "marital_status": ["marital_status"],
        "education_level": ["education_level"],
        "employer_name": ["current_employer"],
        "position": ["current_position"],
        "monthly_salary": ["monthly_salary"],
    }

    extra: dict[str, dict[str, list[str]]] = {
        "ID990A": {
            "employer_address": ["address_hk"],
            "purpose_of_extension": [],
        },
        "ID990B": {
            "current_employer_name": ["current_employer"],
            "current_position": ["current_position"],
            "current_salary": ["monthly_salary"],
        },
        "GEP": {
            "residential_address_overseas": ["address_overseas"],
            "employer_br_number": [],
            "employer_nature": [],
            "education_institution": [],
            "education_major": [],
        },
        "ASMTP": {
            "surname_zh": [],
            "given_name_zh": [],
            "mainland_id_number": [],
            "residential_address_mainland": ["address_overseas"],
            "contact_phone_mainland": ["phone"],
        },
        "QMAS": {
            "age_at_application": [],
            "education_institution": [],
            "education_major": [],
            "work_experience_years": [],
            "language_proficiency": [],
            "financial_proof": [],
        },
        "IANG": {
            "institution_name": [],
            "programme_title": [],
            "qualification_level": ["education_level"],
            "graduation_date": [],
            "student_id": [],
            "application_type": [],
        },
    }

    merged = dict(common)
    ft = form_type.upper()
    if ft in extra:
        for field_name, keys in extra[ft].items():
            if field_name not in merged:
                merged[field_name] = keys
            else:
                merged[field_name] = keys or merged[field_name]

    return merged


def _transform(value: Any, field_def: dict[str, Any]) -> Any:
    """Apply formatting rules to a single value."""
    if value is None:
        return value

    str_val = str(value)

    if field_def["field_type"] == "date":
        return _to_ddmmyyyy(str_val)

    if field_def["field_type"] == "number":
        return str_val

    if field_def["field_type"] == "text" and str_val.isascii():
        return str_val.upper()

    return str_val


def _to_ddmmyyyy(val: str) -> str:
    """Convert YYYY-MM-DD or other common formats to DD/MM/YYYY."""
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%Y%m%d"):
        try:
            dt = datetime.strptime(val, fmt)
            return dt.strftime("%d/%m/%Y")
        except ValueError:
            continue
    return val
