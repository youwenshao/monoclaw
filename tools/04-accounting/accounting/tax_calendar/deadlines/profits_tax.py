"""HK Profits Tax deadline rules for BIR51 (corporations) and BIR52 (unincorporated)."""

from __future__ import annotations

from datetime import date
from typing import Any


def calculate_profits_tax(
    client: dict, ird_code: str, assessment_year: str, config: dict
) -> list[dict]:
    """Calculate Profits Tax filing deadlines based on IRD code category.

    IRD issues bulk returns on the first working day of April each year:
    - "D" code (Dec year-end): Original due mid-August, block extension to mid-November
    - "M" code (Mar year-end): Original due mid-November, block extension to mid-January (next year)
    - "N" code (other):        Original due early May, limited extension to end of May
    """
    parts = assessment_year.split("/")
    start_year = int(parts[0])
    end_suffix = parts[1] if len(parts) > 1 else str(start_year + 1)[-2:]
    end_year = int(str(start_year)[:2] + end_suffix)

    form_code = _form_code(client.get("company_type", "corporation"))
    original_due, block_ext_due = _due_dates(ird_code, end_year, config)

    deadline: dict[str, Any] = {
        "client_id": client["id"],
        "deadline_type": "profits_tax",
        "form_code": form_code,
        "assessment_year": assessment_year,
        "original_due_date": original_due,
        "extended_due_date": block_ext_due,
        "extension_type": "block" if block_ext_due else None,
        "extension_status": "granted" if block_ext_due else None,
        "filing_status": "not_started",
    }
    return [deadline]


def _form_code(company_type: str) -> str:
    """BIR51 for corporations, BIR52 for partnerships / sole proprietors."""
    if company_type == "corporation":
        return "BIR51"
    return "BIR52"


def _due_dates(ird_code: str, end_year: int, config: dict) -> tuple[date, date | None]:
    """Return (original_due_date, block_extension_date) for the given code."""
    ext_overrides = config.get("extra", {}).get("block_extension_dates", {})

    if ird_code == "D":
        original = date(end_year, 8, 15)
        ext_key = "D_code"
        default_ext = date(end_year, 11, 15)
    elif ird_code == "M":
        original = date(end_year, 11, 15)
        ext_key = "M_code"
        default_ext = date(end_year + 1, 1, 15)
    else:
        original = date(end_year, 5, 3)
        ext_key = "N_code"
        default_ext = date(end_year, 5, 31)

    if ext_key in ext_overrides:
        ext_date_str = ext_overrides[ext_key]
        ext = date.fromisoformat(ext_date_str) if isinstance(ext_date_str, str) else ext_date_str
    else:
        ext = default_ext

    return original, ext


def profits_tax_summary(ird_code: str) -> dict[str, str]:
    """Human-readable summary of the code's filing schedule."""
    summaries = {
        "D": {
            "code": "D",
            "year_end": "December",
            "original_deadline": "Mid-August",
            "block_extension": "Mid-November",
            "note": "Largest group; HKICPA negotiates block extension annually.",
        },
        "M": {
            "code": "M",
            "year_end": "March",
            "original_deadline": "Mid-November",
            "block_extension": "Mid-January (following year)",
            "note": "Common for HK-incorporated companies. Extension crosses year boundary.",
        },
        "N": {
            "code": "N",
            "year_end": "Other (non-Dec, non-Mar)",
            "original_deadline": "Early May",
            "block_extension": "End of May (limited)",
            "note": "Shortest extension window. Plan filing early.",
        },
    }
    return summaries.get(ird_code, {"code": ird_code, "note": "Unknown code"})
