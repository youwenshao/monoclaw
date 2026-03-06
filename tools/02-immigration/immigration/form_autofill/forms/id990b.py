"""ID990B — Application for Change of Sponsorship / Employment."""

from __future__ import annotations

from typing import Any

from immigration.form_autofill.forms.base import FormDefinition, register_form


@register_form
class ID990BForm(FormDefinition):
    form_type = "ID990B"
    form_name = "Application for Change of Employment / Change of Sponsorship"
    version = "2024-01"

    def get_field_list(self) -> list[dict[str, Any]]:
        f = self._field
        return [
            # Applicant details
            f("surname_en", "Surname (English)", page=1, max_chars=40),
            f("given_name_en", "Given Name(s) (English)", page=1, max_chars=60),
            f("name_zh", "Chinese Name", page=1, max_chars=20, required=False,
              format_hint="Chinese characters"),
            f("sex", "Sex", page=1, max_chars=6, format_hint="Male / Female"),
            f("date_of_birth", "Date of Birth", page=1, max_chars=10, field_type="date",
              format_hint="DD/MM/YYYY"),
            f("nationality", "Nationality", page=1, max_chars=40),
            f("passport_number", "Travel Document No.", page=1, max_chars=20),
            f("passport_expiry_date", "Passport Expiry Date", page=1, max_chars=10,
              field_type="date", format_hint="DD/MM/YYYY"),
            f("hkid", "HKID Card No.", page=1, max_chars=12, required=False,
              format_hint="e.g. A123456(7)"),
            f("current_visa_type", "Present Condition of Stay", page=1, max_chars=40),
            f("current_visa_expiry", "Limit of Stay", page=1, max_chars=10, field_type="date",
              format_hint="DD/MM/YYYY"),
            f("residential_address", "Residential Address in HK", page=1, max_chars=120),
            f("contact_phone", "Telephone No.", page=1, max_chars=20),
            # Current (old) employer
            f("current_employer_name", "Current Employer Name", page=2, max_chars=60),
            f("current_employer_address", "Current Employer Address", page=2, max_chars=120),
            f("current_position", "Current Position", page=2, max_chars=60),
            f("current_salary", "Current Monthly Salary (HK$)", page=2, max_chars=12,
              field_type="number"),
            f("employment_start_date", "Date Employment Commenced", page=2, max_chars=10,
              field_type="date", format_hint="DD/MM/YYYY"),
            f("reason_for_change", "Reason for Change", page=2, max_chars=200),
            # New employer
            f("new_employer_name", "New Employer Name", page=3, max_chars=60),
            f("new_employer_address", "New Employer Address", page=3, max_chars=120),
            f("new_employer_br_number", "New Employer BR No.", page=3, max_chars=20,
              format_hint="Business Registration number"),
            f("new_position", "New Position / Job Title", page=3, max_chars=60),
            f("new_salary", "New Monthly Salary (HK$)", page=3, max_chars=12,
              field_type="number"),
            f("new_employment_start", "Proposed Commencement Date", page=3, max_chars=10,
              field_type="date", format_hint="DD/MM/YYYY"),
            f("new_job_duties", "Brief Description of Duties", page=3, max_chars=300),
            f("declaration_signed", "Declaration Signed", page=4, max_chars=1,
              field_type="checkbox", format_hint="Y/N"),
        ]

    def validate(self, field_values: dict[str, Any]) -> dict[str, Any]:
        result = self._validate_common(field_values)

        new_employer = field_values.get("new_employer_name", "")
        old_employer = field_values.get("current_employer_name", "")
        if new_employer and old_employer and new_employer.upper() == old_employer.upper():
            result["warnings"].append({
                "field": "new_employer_name",
                "message": "New employer is the same as current employer — "
                           "use ID990A for extension of stay instead",
            })

        result["valid"] = len(result["errors"]) == 0
        return result

    def get_checklist(self) -> list[dict[str, Any]]:
        return [
            {"name": "Completed application form ID990B", "required": True,
             "notes": "Signed by applicant"},
            {"name": "Copy of travel document (bio-data page)", "required": True,
             "notes": "All visa labels and entry/exit stamps"},
            {"name": "Copy of current visa label", "required": True, "notes": ""},
            {"name": "Copy of HKID card (both sides)", "required": True, "notes": "If applicable"},
            {"name": "Recent photograph (40mm × 50mm)", "required": True,
             "notes": "Taken within last 6 months"},
            {"name": "Current employer's release letter", "required": True,
             "notes": "Confirming termination / acceptance of change"},
            {"name": "New employer's offer letter", "required": True,
             "notes": "Stating position, salary, duties, and start date"},
            {"name": "New employer's Business Registration Certificate copy", "required": True,
             "notes": ""},
            {"name": "New employer's company profile / brochure", "required": False,
             "notes": "Including financial statements if new company"},
        ]
