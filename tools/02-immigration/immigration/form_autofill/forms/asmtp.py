"""ASMTP — Admission Scheme for Mainland Talents and Professionals."""

from __future__ import annotations

from typing import Any

from immigration.form_autofill.forms.base import FormDefinition, register_form


@register_form
class ASMTPForm(FormDefinition):
    form_type = "ASMTP"
    form_name = "Admission Scheme for Mainland Talents and Professionals (輸入內地人才計劃)"
    version = "2024-02"

    def get_field_list(self) -> list[dict[str, Any]]:
        f = self._field
        return [
            # Part A — Applicant particulars
            f("surname_zh", "Chinese Surname (姓)", page=1, max_chars=10,
              format_hint="Chinese characters"),
            f("given_name_zh", "Chinese Given Name (名)", page=1, max_chars=20,
              format_hint="Chinese characters"),
            f("surname_en", "Surname (English)", page=1, max_chars=40),
            f("given_name_en", "Given Name(s) (English)", page=1, max_chars=60),
            f("sex", "Sex", page=1, max_chars=6, format_hint="Male / Female"),
            f("date_of_birth", "Date of Birth", page=1, max_chars=10, field_type="date",
              format_hint="DD/MM/YYYY"),
            f("place_of_birth", "Place of Birth (Mainland China)", page=1, max_chars=40),
            f("nationality", "Nationality", page=1, max_chars=40, format_hint="Chinese"),
            f("mainland_id_number", "Mainland ID Card No. (居民身份證號碼)", page=1,
              max_chars=18, format_hint="18-digit ID number"),
            f("eep_number", "Exit-Entry Permit No. (往來港澳通行證號碼)", page=1,
              max_chars=12, required=False,
              format_hint="If already holding EEP"),
            f("passport_number", "PRC Passport No.", page=1, max_chars=20, required=False,
              format_hint="If applicable"),
            f("residential_address_mainland", "Residential Address (Mainland)", page=1,
              max_chars=200),
            f("contact_phone_mainland", "Mainland Telephone No.", page=1, max_chars=20),
            f("contact_email", "Email Address", page=1, max_chars=60),
            f("marital_status", "Marital Status", page=1, max_chars=12,
              format_hint="Single / Married / Divorced / Widowed"),
            # Part B — Education
            f("education_level", "Highest Education Level", page=2, max_chars=40),
            f("education_institution", "Name of Institution", page=2, max_chars=80),
            f("education_major", "Major / Field of Study", page=2, max_chars=60),
            # Part C — HK employment offer
            f("employer_name", "HK Employer / Company Name", page=3, max_chars=60),
            f("employer_address", "HK Employer Address", page=3, max_chars=120),
            f("employer_br_number", "Business Registration No.", page=3, max_chars=20),
            f("position", "Position / Job Title", page=3, max_chars=60),
            f("monthly_salary", "Monthly Salary (HK$)", page=3, max_chars=12,
              field_type="number"),
            f("job_duties", "Detailed Job Duties", page=3, max_chars=500),
            f("employment_start_date", "Proposed Employment Start Date", page=3, max_chars=10,
              field_type="date", format_hint="DD/MM/YYYY"),
            f("has_confirmed_hk_offer", "Confirmed HK Employment Offer", page=3, max_chars=1,
              field_type="checkbox", format_hint="Y/N — must be confirmed before application"),
            f("declaration_signed", "Declaration Signed", page=4, max_chars=1,
              field_type="checkbox", format_hint="Y/N"),
        ]

    def validate(self, field_values: dict[str, Any]) -> dict[str, Any]:
        result = self._validate_common(field_values)

        nationality = field_values.get("nationality", "").upper()
        if nationality and nationality != "CHINESE":
            result["errors"].append({
                "field": "nationality",
                "message": "ASMTP is exclusively for Chinese Mainland residents",
            })

        mainland_id = field_values.get("mainland_id_number", "")
        if mainland_id and len(mainland_id) != 18:
            result["errors"].append({
                "field": "mainland_id_number",
                "message": "Mainland ID card number must be 18 digits",
            })

        offer_confirmed = field_values.get("has_confirmed_hk_offer", "")
        if str(offer_confirmed).upper() not in ("Y", "1", "TRUE"):
            result["errors"].append({
                "field": "has_confirmed_hk_offer",
                "message": "Applicant must have a confirmed HK employment offer before applying",
            })

        result["valid"] = len(result["errors"]) == 0
        return result

    def get_checklist(self) -> list[dict[str, Any]]:
        return [
            {"name": "Completed application form", "required": True,
             "notes": "Signed by both applicant and HK sponsor"},
            {"name": "Copy of Mainland ID card (both sides)", "required": True, "notes": ""},
            {"name": "Copy of Exit-Entry Permit for HK & Macao", "required": False,
             "notes": "If already holding"},
            {"name": "Recent photograph (40mm × 50mm)", "required": True,
             "notes": "White background"},
            {"name": "Copy of academic certificates", "required": True,
             "notes": "Verified by PRC Ministry of Education if needed"},
            {"name": "Proof of relevant work experience", "required": True,
             "notes": "Reference letters, social insurance records"},
            {"name": "HK employer's letter confirming employment offer", "required": True,
             "notes": "Stating position, salary, duties"},
            {"name": "Employment contract", "required": True,
             "notes": "Signed by both parties"},
            {"name": "Employer's Business Registration Certificate", "required": True,
             "notes": ""},
            {"name": "Employer's company profile / financial statements", "required": True,
             "notes": ""},
        ]
