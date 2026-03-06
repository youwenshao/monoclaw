"""ID990A — Application for Extension of Stay (Visa Extension)."""

from __future__ import annotations

from typing import Any

from immigration.form_autofill.forms.base import FormDefinition, register_form


@register_form
class ID990AForm(FormDefinition):
    form_type = "ID990A"
    form_name = "Application for Extension of Stay in / Permission to Remain in Hong Kong"
    version = "2024-01"

    def get_field_list(self) -> list[dict[str, Any]]:
        f = self._field
        return [
            f("surname_en", "Surname (English)", page=1, max_chars=40),
            f("given_name_en", "Given Name(s) (English)", page=1, max_chars=60),
            f("name_zh", "Chinese Name (中文姓名)", page=1, max_chars=20, required=False,
              format_hint="Chinese characters"),
            f("alias", "Alias / Other Names", page=1, max_chars=60, required=False),
            f("sex", "Sex", page=1, max_chars=6, format_hint="Male / Female"),
            f("date_of_birth", "Date of Birth", page=1, max_chars=10, field_type="date",
              format_hint="DD/MM/YYYY"),
            f("place_of_birth", "Place of Birth", page=1, max_chars=40),
            f("nationality", "Nationality", page=1, max_chars=40),
            f("passport_number", "Travel Document No.", page=1, max_chars=20),
            f("passport_issue_place", "Place of Issue", page=1, max_chars=40),
            f("passport_issue_date", "Date of Issue", page=1, max_chars=10, field_type="date",
              format_hint="DD/MM/YYYY"),
            f("passport_expiry_date", "Date of Expiry", page=1, max_chars=10, field_type="date",
              format_hint="DD/MM/YYYY"),
            f("hkid", "HKID Card No.", page=1, max_chars=12, required=False,
              format_hint="e.g. A123456(7)"),
            f("current_visa_type", "Present Condition of Stay", page=2, max_chars=40,
              format_hint="e.g. Employment / Student / Dependant"),
            f("current_visa_expiry", "Limit of Stay", page=2, max_chars=10, field_type="date",
              format_hint="DD/MM/YYYY"),
            f("residential_address", "Residential Address in HK", page=2, max_chars=120),
            f("contact_phone", "Telephone No.", page=2, max_chars=20),
            f("employer_name", "Name of Employer / School", page=2, max_chars=60),
            f("employer_address", "Address of Employer / School", page=2, max_chars=120),
            f("position", "Position / Course of Study", page=2, max_chars=60),
            f("monthly_salary", "Monthly Salary (HK$)", page=2, max_chars=12, field_type="number",
              format_hint="Numbers only"),
            f("marital_status", "Marital Status", page=2, max_chars=12,
              format_hint="Single / Married / Divorced / Widowed"),
            f("purpose_of_extension", "Purpose of Extension", page=3, max_chars=200),
            f("declaration_signed", "Declaration Signed", page=3, max_chars=1, field_type="checkbox",
              format_hint="Y/N"),
        ]

    def validate(self, field_values: dict[str, Any]) -> dict[str, Any]:
        result = self._validate_common(field_values)

        passport_expiry = field_values.get("passport_expiry_date", "")
        if passport_expiry:
            from datetime import datetime
            try:
                exp = datetime.strptime(passport_expiry, "%d/%m/%Y")
                if exp < datetime.now():
                    result["errors"].append({
                        "field": "passport_expiry_date",
                        "message": "Passport has expired — applicant must renew before applying",
                    })
            except ValueError:
                pass

        result["valid"] = len(result["errors"]) == 0
        return result

    def get_checklist(self) -> list[dict[str, Any]]:
        return [
            {"name": "Completed application form ID990A", "required": True,
             "notes": "Signed by applicant"},
            {"name": "Copy of applicant's travel document (bio-data page)", "required": True,
             "notes": "Including all visa labels and entry/exit stamps"},
            {"name": "Copy of current visa label", "required": True, "notes": ""},
            {"name": "Copy of HKID card (both sides)", "required": True, "notes": "If applicable"},
            {"name": "Recent photograph (40mm × 50mm)", "required": True,
             "notes": "Taken within last 6 months, white background"},
            {"name": "Employer's letter confirming employment", "required": True,
             "notes": "Stating position, salary, and period of employment"},
            {"name": "Copy of employment contract", "required": True,
             "notes": "Current or renewed contract"},
            {"name": "Proof of accommodation in HK", "required": False,
             "notes": "Tenancy agreement or utility bill"},
        ]
