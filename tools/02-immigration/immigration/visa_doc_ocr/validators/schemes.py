"""Hong Kong immigration scheme document requirements."""

from __future__ import annotations

SCHEME_REQUIREMENTS: dict[str, list[str]] = {
    "GEP": [
        "passport",
        "employment_contract",
        "bank_statement",
        "tax_return",
        "degree_certificate",
        "employer_br",
        "company_profile",
        "job_description",
        "salary_proof",
    ],
    "ASMTP": [
        "passport",
        "employment_contract",
        "bank_statement",
        "tax_return",
        "degree_certificate",
        "employer_br",
        "company_profile",
        "job_description",
        "salary_proof",
        "transfer_letter",
    ],
    "QMAS": [
        "passport",
        "bank_statement",
        "tax_return",
        "degree_certificate",
        "degree_transcript",
        "cv",
        "proof_of_experience",
        "professional_qualification",
        "achievement_awards",
    ],
    "TTPS": [
        "passport",
        "degree_certificate",
        "salary_proof",
        "employment_proof",
        "tax_return",
    ],
    "IANG": [
        "passport",
        "degree_certificate",
        "degree_transcript",
        "employment_contract",
        "employer_br",
    ],
    "Dependant": [
        "passport",
        "sponsor_passport",
        "sponsor_hkid",
        "relationship_proof",
        "sponsor_employment_proof",
        "sponsor_income_proof",
        "sponsor_accommodation_proof",
    ],
}

SCHEME_LABELS: dict[str, str] = {
    "GEP": "General Employment Policy",
    "ASMTP": "Admission Scheme for Mainland Talents and Professionals",
    "QMAS": "Quality Migrant Admission Scheme",
    "TTPS": "Top Talent Pass Scheme",
    "IANG": "Immigration Arrangements for Non-local Graduates",
    "Dependant": "Dependant Visa",
}
