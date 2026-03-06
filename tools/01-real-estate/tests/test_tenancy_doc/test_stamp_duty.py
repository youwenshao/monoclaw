"""Tests for TenancyDoc stamp duty calculator — verifies IRD published rates."""

import pytest


def test_one_year_term():
    """Stamp duty for 1-year term: 0.25% of total rent."""
    from real_estate.tenancy_doc.generators.stamp_duty import calculate_stamp_duty
    result = calculate_stamp_duty(monthly_rent=20000, term_months=12)
    total_rent = 20000 * 12
    expected_duty = total_rent * 0.0025
    assert result["total_rent"] == total_rent
    assert abs(result["duty_amount"] - expected_duty) < 1


def test_two_year_term():
    """Stamp duty for 2-year term: 0.5% of average yearly rent."""
    from real_estate.tenancy_doc.generators.stamp_duty import calculate_stamp_duty
    result = calculate_stamp_duty(monthly_rent=20000, term_months=24)
    avg_yearly = 20000 * 12
    expected_duty = avg_yearly * 0.005
    assert abs(result["duty_amount"] - expected_duty) < 1


def test_three_year_plus_term():
    """Stamp duty for 3+ year term: 1% of average yearly rent."""
    from real_estate.tenancy_doc.generators.stamp_duty import calculate_stamp_duty
    result = calculate_stamp_duty(monthly_rent=20000, term_months=40)
    avg_yearly = 20000 * 12
    expected_duty = avg_yearly * 0.01
    assert abs(result["duty_amount"] - expected_duty) < 1


def test_result_structure():
    from real_estate.tenancy_doc.generators.stamp_duty import calculate_stamp_duty
    result = calculate_stamp_duty(monthly_rent=15000, term_months=24)
    assert "total_rent" in result
    assert "average_yearly_rent" in result
    assert "rate_applied" in result
    assert "duty_amount" in result
