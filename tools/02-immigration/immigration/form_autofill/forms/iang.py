"""IANG — Immigration Arrangements for Non-local Graduates."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from immigration.form_autofill.forms.base import FormDefinition, register_form


@register_form
class IANGForm(FormDefinition):
    form_type = "IANG"
    form_name = "Immigration Arrangements for Non-local Graduates (非本地畢業生留港/回港就業安排)"
    version = "2024-02"

    def get_field_list(self) -> list[dict[str, Any]]:
        f = self._field
        return [
            # Part A — Personal
            f("surname_en", "Surname (English)", page=1, max_chars=40),
            f("given_name_en", "Given Name(s) (English)", page=1, max_chars=60),
            f("name_zh", "Chinese Name", page=1, max_chars=20, required=False,
              format_hint="Chinese characters"),
            f("sex", "Sex", page=1, max_chars=6, format_hint="Male / Female"),
            f("date_of_birth", "Date of Birth", page=1, max_chars=10, field_type="date",
              format_hint="DD/MM/YYYY"),
            f("place_of_birth", "Place of Birth", page=1, max_chars=40),
            f("nationality", "Nationality", page=1, max_chars=40),
            f("passport_number", "Travel Document No.", page=1, max_chars=20),
            f("passport_expiry_date", "Passport Expiry Date", page=1, max_chars=10,
              field_type="date", format_hint="DD/MM/YYYY"),
            f("hkid", "HKID Card No.", page=1, max_chars=12, required=False,
              format_hint="e.g. A123456(7)"),
            f("residential_address", "Residential Address in HK", page=1, max_chars=120),
            f("contact_phone", "Telephone No.", page=1, max_chars=20),
            f("contact_email", "Email Address", page=1, max_chars=60),
            # Part B — Academic record
            f("institution_name", "Name of HK Institution", page=2, max_chars=80),
            f("programme_title", "Programme Title", page=2, max_chars=100),
            f("qualification_level", "Qualification Obtained", page=2, max_chars=40,
              format_hint="e.g. Bachelor / Postgraduate Diploma / Master / Doctorate"),
            f("graduation_date", "Date of Graduation", page=2, max_chars=10, field_type="date",
              format_hint="DD/MM/YYYY — must apply within 6 months"),
            f("student_id", "Student ID No.", page=2, max_chars=20),
            # Part C — Employment (if returning graduate applying for employment)
            f("employer_name", "Employer Name", page=3, max_chars=60, required=False,
              format_hint="Leave blank if applying before securing employment"),
            f("employer_address", "Employer Address", page=3, max_chars=120, required=False),
            f("position", "Position / Job Title", page=3, max_chars=60, required=False),
            f("monthly_salary", "Monthly Salary (HK$)", page=3, max_chars=12,
              field_type="number", required=False),
            f("application_type", "Application Type", page=3, max_chars=20,
              format_hint="FRESH (within 6 months) or RETURNING"),
            f("declaration_signed", "Declaration Signed", page=4, max_chars=1,
              field_type="checkbox", format_hint="Y/N"),
        ]

    def validate(self, field_values: dict[str, Any]) -> dict[str, Any]:
        result = self._validate_common(field_values)

        grad_date_str = field_values.get("graduation_date", "")
        if grad_date_str:
            try:
                grad_date = datetime.strptime(grad_date_str, "%d/%m/%Y")
                months_since = (datetime.now() - grad_date).days / 30.44
                if months_since > 6 and (
                    field_values.get("application_type", "").upper() != "RETURNING"
                ):
                    result["errors"].append({
                        "field": "graduation_date",
                        "message": (
                            f"Graduated {months_since:.0f} months ago — "
                            "fresh graduates must apply within 6 months. "
                            "If >6 months, applicant may qualify under "
                            "'returning non-local graduate' track instead."
                        ),
                    })
                elif months_since > 6:
                    result["warnings"].append({
                        "field": "graduation_date",
                        "message": "Returning graduate — must demonstrate HK employment offer",
                    })
            except ValueError:
                pass

        app_type = (field_values.get("application_type") or "").upper()
        if app_type == "RETURNING":
            if not field_values.get("employer_name"):
                result["errors"].append({
                    "field": "employer_name",
                    "message": "Returning graduates must have a confirmed HK employer",
                })

        result["valid"] = len(result["errors"]) == 0
        return result

    def get_checklist(self) -> list[dict[str, Any]]:
        return [
            {"name": "Completed application form", "required": True,
             "notes": "Signed by applicant"},
            {"name": "Copy of travel document (bio-data page)", "required": True, "notes": ""},
            {"name": "Copy of HKID card (both sides)", "required": True,
             "notes": "If applicable"},
            {"name": "Recent photograph (40mm × 50mm)", "required": True,
             "notes": "White background"},
            {"name": "Copy of graduation certificate / degree", "required": True,
             "notes": "Issued by the HK institution"},
            {"name": "Academic transcript", "required": True,
             "notes": "Official transcript from the institution"},
            {"name": "Confirmation letter from institution", "required": True,
             "notes": "Confirming the applicant was a full-time student"},
            {"name": "Employer's offer letter", "required": False,
             "notes": "Required if already employed or returning graduate"},
            {"name": "Proof of previous student visa / entry permit", "required": True,
             "notes": ""},
        ]
