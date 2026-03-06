"""Tests for copay calculation and HA rate comparison."""

from medical_dental.insurance_agent.estimation.copay_calculator import CopayCalculator
from medical_dental.insurance_agent.estimation.ha_rate_lookup import compare_rates


def test_percentage_copay():
    calc = CopayCalculator()
    result = calc.calculate(
        "gp_consultation",
        800.0,
        {"copay_percentage": 20, "copay_fixed": 0, "deductible": 0, "sub_limit": 0},
    )
    assert result["billed_amount"] == 800.0
    assert result["patient_copay"] == 160.0
    assert result["insurer_pays"] == 640.0
    assert result["deductible_applied"] == 0.0


def test_fixed_copay():
    calc = CopayCalculator()
    result = calc.calculate(
        "gp_consultation",
        500.0,
        {"copay_percentage": 0, "copay_fixed": 50, "deductible": 0, "sub_limit": 0},
    )
    assert result["billed_amount"] == 500.0
    assert result["patient_copay"] == 50.0
    assert result["insurer_pays"] == 450.0


def test_copay_with_deductible():
    calc = CopayCalculator()
    result = calc.calculate(
        "dental_major",
        2000.0,
        {
            "copay_percentage": 20,
            "copay_fixed": 0,
            "deductible": 500,
            "deductible_met": 0,
            "sub_limit": 0,
        },
    )
    assert result["deductible_applied"] == 500.0
    amount_after_deductible = 2000.0 - 500.0  # 1500
    patient_share = amount_after_deductible * 0.20  # 300
    expected_patient = 500.0 + patient_share  # 800
    assert result["patient_copay"] == expected_patient
    assert result["insurer_pays"] == 2000.0 - expected_patient


def test_sublimit_exceeded():
    calc = CopayCalculator()
    result = calc.calculate(
        "specialist",
        3000.0,
        {
            "copay_percentage": 20,
            "copay_fixed": 0,
            "deductible": 0,
            "sub_limit": 2000,
        },
    )
    excess = 3000.0 - 2000.0  # 1000 exceeds sub-limit
    patient_from_copay = 2000.0 * 0.20  # 400 on the capped amount
    insurer_pays = 2000.0 - patient_from_copay  # 1600
    patient_total = 3000.0 - insurer_pays  # 1400

    assert result["insurer_pays"] == insurer_pays
    assert result["patient_copay"] == patient_total
    assert any("sub-limit" in n.lower() for n in result["notes"])


def test_ha_rate_comparison():
    result = compare_rates("gp_consultation", 500.0)

    assert result["procedure"] == "gp_consultation"
    assert result["private_fee"] == 500.0
    assert result["public_fee"] == 50.0
    assert result["difference"] == 450.0
    assert result["savings_ratio"] == round(450.0 / 500.0, 4)
    assert result["currency"] == "HKD"
