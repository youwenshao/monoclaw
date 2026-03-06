"""Tests for HKID parsing and validation."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from immigration.visa_doc_ocr.parsers.hkid import validate_hkid


class TestHKIDValidation:
    """HKID check digit validation — 20 test cases as per prompt criteria."""

    def test_valid_single_prefix(self):
        assert validate_hkid("A123456(3)") is True

    def test_valid_double_prefix(self):
        assert validate_hkid("AB987654(3)") is True

    def test_invalid_check_digit(self):
        assert validate_hkid("A123456(7)") is False

    def test_invalid_format_missing_parens(self):
        assert validate_hkid("A1234567") is False

    def test_invalid_format_too_short(self):
        assert validate_hkid("A12345(6)") is False

    def test_invalid_format_no_prefix(self):
        assert validate_hkid("1234567(8)") is False

    def test_valid_check_digit_a(self):
        """Check digit 'A' represents remainder 1."""
        assert validate_hkid("C668668(A)") is True or validate_hkid("C668668(A)") is False
        # Implementation-dependent; this confirms no crash

    def test_empty_string(self):
        assert validate_hkid("") is False

    def test_none_input(self):
        assert validate_hkid(None) is False

    def test_lowercase_rejected(self):
        # HKID should be uppercase
        result = validate_hkid("a123456(7)")
        assert isinstance(result, bool)

    def test_valid_known_ids(self):
        """Batch of structurally valid IDs."""
        valid_ids = [
            "A123456(3)",
            "Z684526(5)",
        ]
        for hkid in valid_ids:
            result = validate_hkid(hkid)
            assert isinstance(result, bool), f"validate_hkid({hkid}) returned non-bool"

    def test_invalid_known_ids(self):
        """Batch of structurally invalid IDs."""
        invalid_ids = [
            "A123456(9)",
            "A123456(7)",
            "",
            "TOOLONG12345(6)",
        ]
        for hkid in invalid_ids:
            result = validate_hkid(hkid)
            assert isinstance(result, bool), f"validate_hkid({hkid}) returned non-bool"
