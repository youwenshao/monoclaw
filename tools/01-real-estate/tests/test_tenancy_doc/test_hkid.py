"""Tests for HKID validation."""

import pytest


def test_valid_hkid():
    from real_estate.tenancy_doc.generators.hkid import validate_hkid
    # Standard single-letter HKID
    assert validate_hkid("G123456(A)") is True or validate_hkid("A123456(7)") is True


def test_invalid_format():
    from real_estate.tenancy_doc.generators.hkid import validate_hkid
    assert validate_hkid("12345678") is False
    assert validate_hkid("") is False
    assert validate_hkid("ABCDEFGH") is False


def test_hkid_format_pattern():
    """HKID should be 1-2 letters + 6 digits + check digit in parens."""
    from real_estate.tenancy_doc.generators.hkid import validate_hkid
    # Missing parentheses
    assert validate_hkid("A1234567") is False
    # Too many letters
    assert validate_hkid("ABC123456(7)") is False
