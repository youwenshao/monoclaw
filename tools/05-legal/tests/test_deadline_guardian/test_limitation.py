"""Tests for limitation period calculation (Cap 347)."""

from datetime import date

import pytest

from legal.deadline_guardian.limitation import calculate_limitation


def test_contract_6_years():
    result = calculate_limitation("contract", date(2026, 1, 1), holidays=[])

    assert result["claim_type"] == "contract"
    assert result["limitation_years"] == 6
    assert result["raw_deadline"] == "2032-01-01"
    assert result["deadline_date"] == "2032-01-01"
    assert result["statutory_basis"] == "Cap 347 s.4"


def test_personal_injury_3_years():
    result = calculate_limitation("personal_injury", date(2026, 1, 1), holidays=[])

    assert result["claim_type"] == "personal_injury"
    assert result["limitation_years"] == 3
    assert result["raw_deadline"] == "2029-01-01"
    assert result["statutory_basis"] == "Cap 347 s.4A"


def test_defamation_1_year():
    result = calculate_limitation("defamation", date(2026, 1, 1), holidays=[])

    assert result["claim_type"] == "defamation"
    assert result["limitation_years"] == 1
    assert result["raw_deadline"] == "2027-01-01"
    assert result["statutory_basis"] == "Cap 347 s.27"


def test_latent_damage_3_years():
    result = calculate_limitation("latent_damage", date(2026, 1, 1), holidays=[])

    assert result["claim_type"] == "latent_damage"
    assert result["limitation_years"] == 3
    assert result["raw_deadline"] == "2029-01-01"
    assert result["statutory_basis"] == "Cap 347 s.4C"


def test_invalid_claim_type():
    with pytest.raises(ValueError, match="Unknown claim type"):
        calculate_limitation("unknown_type", date(2026, 1, 1))


def test_holiday_rollover():
    """2026-07-01 (HKSAR Establishment Day) is in default HK holidays."""
    result = calculate_limitation("defamation", date(2025, 7, 1))

    assert result["raw_deadline"] == "2026-07-01"
    assert result["deadline_date"] != result["raw_deadline"]
    assert result["deadline_date"] == "2026-07-02"
