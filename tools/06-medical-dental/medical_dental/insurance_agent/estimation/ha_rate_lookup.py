"""Hong Kong Hospital Authority public rates for comparison."""

from __future__ import annotations

from typing import Any

HA_PUBLIC_RATES: dict[str, dict[str, Any]] = {
    "gp_consultation": {
        "description": "General Out-patient Clinic",
        "fee": 50,
        "currency": "HKD",
        "source": "HA GOPC standard charge",
    },
    "specialist": {
        "description": "Specialist Out-patient Clinic (first attendance)",
        "fee": 135,
        "currency": "HKD",
        "source": "HA SOPC standard charge",
    },
    "specialist_followup": {
        "description": "Specialist Out-patient Clinic (follow-up)",
        "fee": 80,
        "currency": "HKD",
        "source": "HA SOPC standard charge",
    },
    "accident_emergency": {
        "description": "Accident & Emergency",
        "fee": 180,
        "currency": "HKD",
        "source": "HA A&E standard charge",
    },
    "dental_checkup": {
        "description": "General dental (HA dental clinics — civil servants / eligible persons)",
        "fee": 0,
        "currency": "HKD",
        "source": "HA dental clinic (eligible persons only)",
    },
    "blood_test": {
        "description": "Included in GOPC / SOPC visit",
        "fee": 0,
        "currency": "HKD",
        "source": "HA standard — included in consultation",
    },
    "x_ray": {
        "description": "Included in consultation visit",
        "fee": 0,
        "currency": "HKD",
        "source": "HA standard — included in consultation",
    },
    "hospitalisation_daily": {
        "description": "Acute general bed (per day)",
        "fee": 120,
        "currency": "HKD",
        "source": "HA inpatient standard charge",
    },
    "follow_up": {
        "description": "General Out-patient follow-up",
        "fee": 50,
        "currency": "HKD",
        "source": "HA GOPC standard charge",
    },
    "physiotherapy": {
        "description": "Allied Health — Physiotherapy (public)",
        "fee": 80,
        "currency": "HKD",
        "source": "HA allied health standard charge",
    },
}


def get_ha_rate(procedure: str) -> dict[str, Any] | None:
    """Return the HA public rate for a procedure, or None if not listed."""
    entry = HA_PUBLIC_RATES.get(procedure)
    if entry is None:
        return None
    return {"procedure": procedure, **entry}


def compare_rates(procedure: str, clinic_fee: float) -> dict[str, Any]:
    """Compare a private clinic fee with the HA public rate.

    Returns a dict with private_fee, public_fee, difference, and savings_ratio.
    """
    ha = HA_PUBLIC_RATES.get(procedure)
    public_fee = ha["fee"] if ha else 0.0
    difference = clinic_fee - public_fee

    savings_ratio = 0.0
    if clinic_fee > 0:
        savings_ratio = round(difference / clinic_fee, 4)

    return {
        "procedure": procedure,
        "private_fee": clinic_fee,
        "public_fee": public_fee,
        "difference": round(difference, 2),
        "savings_ratio": savings_ratio,
        "currency": "HKD",
        "public_source": ha["source"] if ha else "Not available in HA system",
        "note": (
            "HA public rates require eligible residency status and may involve "
            "long waiting times. Dental services limited to civil servants and "
            "eligible categories."
        ),
    }


def list_ha_rates() -> list[dict[str, Any]]:
    """Return all HA public rates."""
    return [{"procedure": k, **v} for k, v in sorted(HA_PUBLIC_RATES.items())]
