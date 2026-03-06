"""Tests for PropertyGPT HK-specific utilities."""

import pytest


def test_mtr_proximity_scoring():
    from real_estate.property_gpt.hk_utils import score_mtr_proximity
    assert score_mtr_proximity(3.0) == "A"
    assert score_mtr_proximity(5.0) == "B"
    assert score_mtr_proximity(7.5) == "B"
    assert score_mtr_proximity(12.0) == "C"
    assert score_mtr_proximity(20.0) == "D"
    assert score_mtr_proximity(None) == "D"


def test_school_net_info():
    from real_estate.property_gpt.hk_utils import get_school_net_info
    info = get_school_net_info(11)
    assert info["net_number"] == 11
    assert "schools" in info

    unknown = get_school_net_info(999)
    assert unknown["net_number"] == 999


def test_format_price_english():
    from real_estate.property_gpt.hk_utils import format_price_hkd
    assert "12.8M" in format_price_hkd(12800000, "en") or "12,800,000" in format_price_hkd(12800000, "en")


def test_format_price_chinese():
    from real_estate.property_gpt.hk_utils import format_price_hkd
    result = format_price_hkd(12800000, "zh")
    assert "萬" in result or "1280" in result


def test_saleable_area_validation():
    from real_estate.property_gpt.hk_utils import validate_saleable_area
    assert validate_saleable_area("Saleable area 583 sqft. Great location.") is True
    assert validate_saleable_area("實用面積583平方呎") is True
    assert validate_saleable_area("Great location near MTR") is False
