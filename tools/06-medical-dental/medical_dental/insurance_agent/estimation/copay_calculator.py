"""Patient co-pay calculation engine."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger("openclaw.medical-dental.insurance.copay")


class CopayCalculator:
    """Calculate patient out-of-pocket costs given clinic fees and coverage details.

    Handles percentage co-insurance, fixed copay, deductibles, and sub-limits.
    """

    def calculate(
        self,
        procedure: str,
        clinic_fee: float,
        coverage_details: dict[str, Any],
    ) -> dict[str, Any]:
        """Compute the co-pay breakdown for a procedure.

        Args:
            procedure: Procedure/benefit category identifier.
            clinic_fee: The clinic's billed amount in HKD.
            coverage_details: Dict with optional keys:
                - copay_percentage: Percentage the patient pays (0–100).
                - copay_fixed: Fixed co-pay amount the patient pays.
                - deductible: Annual deductible amount.
                - deductible_met: How much deductible already satisfied.
                - sub_limit: Maximum insurer pays for this category.
                - annual_remaining: Remaining annual balance.
                - requires_preauth: Whether pre-authorization is needed.

        Returns:
            Dict with billed_amount, insurer_pays, patient_copay,
            deductible_applied, and notes.
        """
        notes: list[str] = []

        copay_pct = coverage_details.get("copay_percentage", 0.0)
        copay_fixed = coverage_details.get("copay_fixed", 0.0)
        deductible = coverage_details.get("deductible", 0.0)
        deductible_met = coverage_details.get("deductible_met", 0.0)
        sub_limit = coverage_details.get("sub_limit", 0.0)
        annual_remaining = coverage_details.get("annual_remaining")
        requires_preauth = coverage_details.get("requires_preauth", False)

        if requires_preauth:
            notes.append("Pre-authorization required for this benefit category")

        deductible_remaining = max(0.0, deductible - deductible_met)
        deductible_applied = min(deductible_remaining, clinic_fee)
        amount_after_deductible = clinic_fee - deductible_applied

        if deductible_applied > 0:
            notes.append(f"Deductible applied: HK${deductible_applied:,.0f}")

        if sub_limit > 0 and amount_after_deductible > sub_limit:
            excess = amount_after_deductible - sub_limit
            amount_after_deductible = sub_limit
            notes.append(
                f"Sub-limit of HK${sub_limit:,.0f} applies; "
                f"HK${excess:,.0f} exceeds sub-limit"
            )

        if copay_fixed > 0:
            patient_share_from_copay = min(copay_fixed, amount_after_deductible)
            insurer_portion = amount_after_deductible - patient_share_from_copay
            notes.append(f"Fixed co-pay: HK${copay_fixed:,.0f}")
        elif copay_pct > 0:
            patient_share_from_copay = round(amount_after_deductible * (copay_pct / 100), 2)
            insurer_portion = amount_after_deductible - patient_share_from_copay
            notes.append(f"Co-insurance: patient pays {copay_pct:.0f}%")
        else:
            patient_share_from_copay = 0.0
            insurer_portion = amount_after_deductible
            notes.append("Fully covered (no co-pay)")

        if annual_remaining is not None and insurer_portion > annual_remaining:
            shortfall = insurer_portion - annual_remaining
            insurer_portion = annual_remaining
            patient_share_from_copay += shortfall
            notes.append(
                f"Annual balance insufficient; additional HK${shortfall:,.0f} "
                "charged to patient"
            )

        patient_copay = round(deductible_applied + patient_share_from_copay, 2)
        insurer_pays = round(insurer_portion, 2)

        if abs(patient_copay + insurer_pays - clinic_fee) > 0.01:
            patient_copay = round(clinic_fee - insurer_pays, 2)

        return {
            "procedure": procedure,
            "billed_amount": clinic_fee,
            "insurer_pays": insurer_pays,
            "patient_copay": patient_copay,
            "deductible_applied": deductible_applied,
            "notes": notes,
            "currency": "HKD",
        }

    def estimate_from_db_coverage(
        self,
        procedure: str,
        clinic_fee: float,
        coverage_row: dict[str, Any],
        policy_remaining: float | None = None,
    ) -> dict[str, Any]:
        """Convenience wrapper that maps DB coverage_details row fields."""
        coverage = {
            "copay_percentage": coverage_row.get("copay_percentage", 0),
            "copay_fixed": coverage_row.get("copay_fixed", 0),
            "deductible": coverage_row.get("deductible", 0),
            "deductible_met": 0.0,
            "sub_limit": coverage_row.get("sub_limit", 0),
            "annual_remaining": policy_remaining,
            "requires_preauth": bool(coverage_row.get("requires_preauth", False)),
        }
        return self.calculate(procedure, clinic_fee, coverage)
