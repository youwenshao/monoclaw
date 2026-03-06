"""Pre-authorization form data generator."""

from __future__ import annotations

import logging
from datetime import date
from typing import Any

logger = logging.getLogger("openclaw.medical-dental.insurance.preauth")


class PreauthFormGenerator:
    """Generate pre-authorization request form data.

    Auto-populates patient details, policy information, and procedure
    descriptions into a structured dict suitable for PDF rendering or
    direct insurer portal submission.
    """

    def generate(
        self,
        patient: dict[str, Any],
        policy: dict[str, Any],
        procedure_description: str,
        estimated_cost: float,
        *,
        clinic_info: dict[str, Any] | None = None,
        diagnosis_code: str = "",
        urgency: str = "elective",
    ) -> dict[str, Any]:
        """Generate a pre-authorization form payload.

        Args:
            patient: Patient record dict (id, name_en, name_tc, phone, date_of_birth).
            policy: Insurance policy dict (policy_number, insurer, member_id, plan_type, etc).
            procedure_description: Free-text description of the proposed procedure.
            estimated_cost: Estimated cost in HKD.
            clinic_info: Optional clinic details for the form header.
            diagnosis_code: ICD-10 code if available.
            urgency: One of "elective", "urgent", "emergency".

        Returns:
            Dict with form_data and pdf_path (placeholder).
        """
        clinic = clinic_info or {}

        form_data: dict[str, Any] = {
            "form_type": "preauthorization_request",
            "generated_date": date.today().isoformat(),
            "urgency": urgency,

            "clinic": {
                "name": clinic.get("clinic_name", ""),
                "address": clinic.get("clinic_address", ""),
                "phone": clinic.get("clinic_phone", ""),
                "hkma_registration": clinic.get("hkma_registration", ""),
                "attending_doctor": clinic.get("attending_doctor", ""),
            },

            "patient": {
                "id": patient.get("id"),
                "name_en": patient.get("name_en", ""),
                "name_tc": patient.get("name_tc", ""),
                "date_of_birth": patient.get("date_of_birth", ""),
                "phone": patient.get("phone", ""),
            },

            "insurance": {
                "insurer": policy.get("insurer", ""),
                "policy_number": policy.get("policy_number", ""),
                "member_id": policy.get("member_id", ""),
                "group_name": policy.get("group_name", ""),
                "plan_type": policy.get("plan_type", ""),
                "effective_date": policy.get("effective_date", ""),
                "expiry_date": policy.get("expiry_date", ""),
            },

            "procedure": {
                "description": procedure_description,
                "diagnosis_code": diagnosis_code,
                "estimated_cost": estimated_cost,
                "currency": "HKD",
                "proposed_date": "",
                "facility": clinic.get("clinic_name", ""),
            },

            "declaration": {
                "text": (
                    "I hereby certify that the information provided is accurate "
                    "and the proposed treatment is medically necessary."
                ),
                "doctor_signature": "",
                "patient_signature": "",
                "date": date.today().isoformat(),
            },
        }

        insurer = policy.get("insurer", "").lower()
        form_data["insurer_specific"] = self._insurer_specific_fields(insurer, policy)

        pdf_path = self._pdf_path_placeholder(patient, policy)

        return {
            "form_data": form_data,
            "pdf_path": pdf_path,
        }

    def _insurer_specific_fields(self, insurer: str, policy: dict[str, Any]) -> dict[str, Any]:
        """Add fields that differ by insurer."""
        if insurer == "bupa":
            return {
                "submission_method": "Bupa member portal or fax +852 2529 2365",
                "expected_turnaround": "3-5 working days",
                "portal_url": "https://www.bupa.com.hk/en/member-login",
            }
        if insurer == "axa":
            return {
                "submission_method": "AXA Emma app or email preauth@axa.com.hk",
                "expected_turnaround": "2-5 working days",
                "portal_url": "https://emma.axa.com.hk/login",
            }
        if insurer == "cigna":
            return {
                "submission_method": "Cigna member portal or call +852 2560 1990",
                "expected_turnaround": "3-5 working days",
                "portal_url": "https://www.cigna.com.hk/member-area/login",
            }
        return {
            "submission_method": "Contact insurer directly",
            "expected_turnaround": "5-10 working days",
            "portal_url": "",
        }

    def _pdf_path_placeholder(self, patient: dict[str, Any], policy: dict[str, Any]) -> str:
        patient_id = patient.get("id", "unknown")
        insurer = policy.get("insurer", "unknown")
        return f"preauth_{insurer}_{patient_id}_{date.today().isoformat()}.pdf"
