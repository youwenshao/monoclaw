"""QMAS — Quality Migrant Admission Scheme (points-based)."""

from __future__ import annotations

from typing import Any

from immigration.form_autofill.forms.base import FormDefinition, register_form

MINIMUM_PASS_SCORE = 80


@register_form
class QMASForm(FormDefinition):
    form_type = "QMAS"
    form_name = "Quality Migrant Admission Scheme (優秀人才入境計劃)"
    version = "2024-02"

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
            f("nationality", "Nationality", page=1, max_chars=40),
            f("passport_number", "Travel Document No.", page=1, max_chars=20),
            f("passport_expiry_date", "Passport Expiry Date", page=1, max_chars=10,
              field_type="date", format_hint="DD/MM/YYYY"),
            f("residential_address", "Residential Address (Overseas)", page=1, max_chars=200),
            f("contact_phone", "Telephone No.", page=1, max_chars=20),
            f("contact_email", "Email Address", page=1, max_chars=60),
            f("marital_status", "Marital Status", page=1, max_chars=12,
              format_hint="Single / Married / Divorced / Widowed"),
            # Part B — Points-test: Age
            f("age_at_application", "Age at Date of Application", page=2, max_chars=3,
              field_type="number", format_hint="18-50; 30 pts for 18-39"),
            # Part B — Points-test: Education
            f("education_level", "Highest Education Level", page=2, max_chars=40,
              format_hint="Doctorate (40) / Master (20) / Bachelor (10)"),
            f("education_institution", "Name of Institution", page=2, max_chars=80),
            f("education_major", "Major / Field of Study", page=2, max_chars=60),
            f("education_year", "Year of Graduation", page=2, max_chars=4, field_type="number"),
            f("institution_is_top_ranked", "Institution in Top 100 (QS/THE)", page=2,
              max_chars=1, field_type="checkbox", required=False,
              format_hint="Bonus 30 pts if internationally recognised"),
            # Part B — Points-test: Work experience
            f("work_experience_years", "Years of Post-Qualification Work Experience", page=2,
              max_chars=3, field_type="number",
              format_hint="10+ yrs: 40 pts; 5-9: 30 pts; 2-4: 10 pts"),
            f("work_experience_hk", "Years of Work Experience in HK", page=2,
              max_chars=3, field_type="number", required=False,
              format_hint="Bonus 5 pts if ≥ 2 years"),
            # Part B — Points-test: Language
            f("language_proficiency", "Language Proficiency", page=3, max_chars=100,
              format_hint="Chinese + English: 20 pts; one of them: 15 pts; plus 3rd language: bonus 5 pts"),
            # Part B — Points-test: Family
            f("accompanying_spouse_education", "Spouse's Highest Education", page=3,
              max_chars=40, required=False,
              format_hint="Bachelor or above: bonus 5 pts"),
            f("minor_children_count", "Number of Accompanying Children Under 18", page=3,
              max_chars=2, field_type="number", required=False,
              format_hint="Each child: bonus 5 pts (max 10 pts)"),
            # Financial
            f("financial_proof", "Proof of Financial Standing", page=3, max_chars=200,
              format_hint="Must demonstrate ability to support self and dependants in HK"),
            # Declaration
            f("declaration_signed", "Declaration Signed", page=4, max_chars=1,
              field_type="checkbox", format_hint="Y/N"),
        ]

    def validate(self, field_values: dict[str, Any]) -> dict[str, Any]:
        result = self._validate_common(field_values)

        points = self.calculate_points(field_values)
        if points["total"] < MINIMUM_PASS_SCORE:
            result["errors"].append({
                "field": "age_at_application",
                "message": (
                    f"General Points Test total is {points['total']} — "
                    f"minimum pass mark is {MINIMUM_PASS_SCORE}. "
                    "Consider Achievement-Based Points Test if the applicant "
                    "has exceptional achievement."
                ),
            })

        age = _safe_int(field_values.get("age_at_application"))
        if age is not None and (age < 18 or age > 50):
            result["errors"].append({
                "field": "age_at_application",
                "message": "Applicant must be aged 18-50 at time of application",
            })

        result["valid"] = len(result["errors"]) == 0
        return result

    def calculate_points(self, field_values: dict[str, Any]) -> dict[str, Any]:
        """Calculate General Points Test score breakdown."""
        breakdown: dict[str, int] = {}

        # Age (max 30)
        age = _safe_int(field_values.get("age_at_application"))
        if age is not None:
            if 18 <= age <= 39:
                breakdown["age"] = 30
            elif 40 <= age <= 44:
                breakdown["age"] = 20
            elif 45 <= age <= 50:
                breakdown["age"] = 15
            else:
                breakdown["age"] = 0
        else:
            breakdown["age"] = 0

        # Education (max 70: 40 degree + 30 top-ranked bonus)
        edu = (field_values.get("education_level") or "").upper()
        if "DOCTOR" in edu or "PHD" in edu:
            breakdown["education"] = 40
        elif "MASTER" in edu:
            breakdown["education"] = 20
        elif "BACHELOR" in edu:
            breakdown["education"] = 10
        else:
            breakdown["education"] = 0

        top_ranked = str(field_values.get("institution_is_top_ranked", "")).upper()
        breakdown["education_bonus"] = 30 if top_ranked in ("Y", "1", "TRUE") else 0

        # Work experience (max 55: 40 base + 5 HK + 10 international)
        exp = _safe_int(field_values.get("work_experience_years"))
        if exp is not None:
            if exp >= 10:
                breakdown["work_experience"] = 40
            elif exp >= 5:
                breakdown["work_experience"] = 30
            elif exp >= 2:
                breakdown["work_experience"] = 10
            else:
                breakdown["work_experience"] = 5
        else:
            breakdown["work_experience"] = 0

        hk_exp = _safe_int(field_values.get("work_experience_hk"))
        breakdown["hk_experience_bonus"] = 5 if hk_exp and hk_exp >= 2 else 0

        # Language (max 20)
        lang = (field_values.get("language_proficiency") or "").upper()
        if "CHINESE" in lang and "ENGLISH" in lang:
            breakdown["language"] = 20
        elif "CHINESE" in lang or "ENGLISH" in lang:
            breakdown["language"] = 15
        else:
            breakdown["language"] = 10

        # Family (max 20)
        spouse_edu = (field_values.get("accompanying_spouse_education") or "").upper()
        breakdown["spouse_bonus"] = 5 if any(
            k in spouse_edu for k in ("BACHELOR", "MASTER", "DOCTOR", "PHD")
        ) else 0

        children = _safe_int(field_values.get("minor_children_count"))
        breakdown["children_bonus"] = min((children or 0) * 5, 10)

        total = sum(breakdown.values())
        return {"breakdown": breakdown, "total": total, "pass": total >= MINIMUM_PASS_SCORE}

    def get_checklist(self) -> list[dict[str, Any]]:
        return [
            {"name": "Completed application form", "required": True,
             "notes": "Signed by applicant"},
            {"name": "Copy of travel document (bio-data page)", "required": True, "notes": ""},
            {"name": "Recent photograph (40mm × 50mm)", "required": True,
             "notes": "White background"},
            {"name": "Copy of academic certificates & transcripts", "required": True,
             "notes": "Notarised if non-HK"},
            {"name": "Proof of work experience", "required": True,
             "notes": "Reference letters and/or employment contracts"},
            {"name": "Proof of language proficiency", "required": True,
             "notes": "IELTS / TOEFL scores or equivalent"},
            {"name": "Proof of financial standing", "required": True,
             "notes": "Bank statements showing ability to support stay"},
            {"name": "Criminal record check from country of residence", "required": True,
             "notes": ""},
            {"name": "Spouse's academic certificates", "required": False,
             "notes": "If claiming family bonus points"},
            {"name": "Children's birth certificates", "required": False,
             "notes": "If claiming family bonus points"},
        ]


def _safe_int(val: Any) -> int | None:
    if val is None:
        return None
    try:
        return int(str(val).replace(",", ""))
    except (ValueError, TypeError):
        return None
