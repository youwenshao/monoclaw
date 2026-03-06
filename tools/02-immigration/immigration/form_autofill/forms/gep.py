"""GEP — General Employment Policy application form."""

from __future__ import annotations

from typing import Any

from immigration.form_autofill.forms.base import FormDefinition, register_form

HK_MARKET_MEDIAN_SALARY = 20000


@register_form
class GEPForm(FormDefinition):
    form_type = "GEP"
    form_name = "Application for Entry for Employment under General Employment Policy"
    version = "2024-03"

    def get_field_list(self) -> list[dict[str, Any]]:
        f = self._field
        return [
            # Part A — Personal particulars
            f("surname_en", "Surname (English)", page=1, max_chars=40),
            f("given_name_en", "Given Name(s) (English)", page=1, max_chars=60),
            f("name_zh", "Chinese Name", page=1, max_chars=20, required=False,
              format_hint="Chinese characters"),
            f("sex", "Sex", page=1, max_chars=6, format_hint="Male / Female"),
            f("date_of_birth", "Date of Birth", page=1, max_chars=10, field_type="date",
              format_hint="DD/MM/YYYY"),
            f("place_of_birth", "Place of Birth", page=1, max_chars=40),
            f("nationality", "Nationality / Citizenship", page=1, max_chars=40),
            f("passport_number", "Travel Document No.", page=1, max_chars=20),
            f("passport_expiry_date", "Passport Expiry Date", page=1, max_chars=10,
              field_type="date", format_hint="DD/MM/YYYY"),
            f("residential_address_overseas", "Overseas Residential Address", page=1,
              max_chars=200),
            f("contact_phone", "Telephone No.", page=1, max_chars=20),
            f("contact_email", "Email Address", page=1, max_chars=60),
            f("marital_status", "Marital Status", page=1, max_chars=12,
              format_hint="Single / Married / Divorced / Widowed"),
            # Part B — Education
            f("education_level", "Highest Education Level", page=2, max_chars=40,
              format_hint="e.g. Bachelor / Master / Doctorate"),
            f("education_institution", "Name of Institution", page=2, max_chars=80),
            f("education_major", "Major / Field of Study", page=2, max_chars=60),
            f("education_year", "Year of Graduation", page=2, max_chars=4, field_type="number"),
            f("professional_qualifications", "Professional Qualifications", page=2,
              max_chars=200, required=False),
            # Part C — Employment in HK
            f("employer_name", "HK Employer Name", page=3, max_chars=60),
            f("employer_address", "HK Employer Address", page=3, max_chars=120),
            f("employer_br_number", "Business Registration No.", page=3, max_chars=20),
            f("employer_nature", "Nature of Business", page=3, max_chars=60),
            f("position", "Position / Job Title", page=3, max_chars=60),
            f("monthly_salary", "Monthly Salary (HK$)", page=3, max_chars=12,
              field_type="number", format_hint=f"Must be ≥ HK${HK_MARKET_MEDIAN_SALARY:,} market median"),
            f("job_duties", "Detailed Job Duties", page=3, max_chars=500),
            f("employment_period_from", "Proposed Employment From", page=3, max_chars=10,
              field_type="date", format_hint="DD/MM/YYYY"),
            f("employment_period_to", "Proposed Employment To", page=3, max_chars=10,
              field_type="date", format_hint="DD/MM/YYYY"),
            f("declaration_signed", "Declaration Signed", page=4, max_chars=1,
              field_type="checkbox", format_hint="Y/N"),
        ]

    def validate(self, field_values: dict[str, Any]) -> dict[str, Any]:
        result = self._validate_common(field_values)

        salary_raw = field_values.get("monthly_salary")
        if salary_raw is not None:
            try:
                salary = int(str(salary_raw).replace(",", ""))
                if salary < HK_MARKET_MEDIAN_SALARY:
                    result["errors"].append({
                        "field": "monthly_salary",
                        "message": (
                            f"Salary HK${salary:,} is below HK market median "
                            f"(HK${HK_MARKET_MEDIAN_SALARY:,}). ImmD may refuse the application "
                            "unless the role is on the Talent List."
                        ),
                    })
            except ValueError:
                result["errors"].append({
                    "field": "monthly_salary",
                    "message": "Salary must be a number",
                })

        result["valid"] = len(result["errors"]) == 0
        return result

    def get_checklist(self) -> list[dict[str, Any]]:
        return [
            {"name": "Completed application form (ID990A used for GEP)", "required": True,
             "notes": "Signed by both applicant and sponsor"},
            {"name": "Copy of travel document (bio-data page)", "required": True,
             "notes": "Including all endorsement pages"},
            {"name": "Recent photograph (40mm × 50mm)", "required": True,
             "notes": "White background, taken within 6 months"},
            {"name": "Copy of academic certificates / transcripts", "required": True,
             "notes": "Notarised if issued outside HK"},
            {"name": "Copy of professional qualifications", "required": False,
             "notes": "If applicable"},
            {"name": "Proof of relevant work experience", "required": True,
             "notes": "Reference letters from previous employers"},
            {"name": "Employer's company profile", "required": True,
             "notes": "Including annual report / audited financial statements"},
            {"name": "Employer's Business Registration Certificate copy", "required": True,
             "notes": ""},
            {"name": "Detailed job description", "required": True,
             "notes": "Why a local worker cannot fill the position"},
            {"name": "Employer's letter of sponsorship", "required": True,
             "notes": "Confirming terms of employment, salary, and sponsorship"},
            {"name": "Employment contract", "required": True,
             "notes": "Signed by both parties"},
            {"name": "Local recruitment evidence", "required": True,
             "notes": "4 weeks of local advertisements to demonstrate efforts"},
        ]
