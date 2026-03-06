"""Hong Kong phone number formatting and validation utilities."""

from __future__ import annotations

import re


def _extract_digits(phone: str) -> str:
    """Strip everything except digits from the input string."""
    return re.sub(r"\D", "", phone)


def format_hk_phone(phone: str) -> str:
    """Format a Hong Kong phone number with +852 country code.

    Accepts raw 8-digit numbers, numbers prefixed with 852, or numbers
    already prefixed with +852. Returns the formatted string ``+852 XXXX XXXX``.

    Raises :class:`ValueError` if the number is not a valid 8-digit HK number.
    """
    digits = _extract_digits(phone)

    if digits.startswith("852") and len(digits) == 11:
        digits = digits[3:]

    if len(digits) != 8:
        raise ValueError(f"HK phone numbers must be 8 digits, got {len(digits)}")

    return f"+852 {digits[:4]} {digits[4:]}"


def is_valid_hk_phone(phone: str) -> bool:
    """Return True if the phone string is a valid 8-digit HK number.

    Valid HK numbers start with 2, 3, 5, 6, 7, or 9.
    """
    digits = _extract_digits(phone)
    if digits.startswith("852") and len(digits) == 11:
        digits = digits[3:]
    return len(digits) == 8 and digits[0] in "235679"


def is_mobile(phone: str) -> bool:
    """Return True if the phone number is a HK mobile number (starts with 5, 6, 7, or 9)."""
    digits = _extract_digits(phone)
    if digits.startswith("852") and len(digits) == 11:
        digits = digits[3:]
    return len(digits) == 8 and digits[0] in "5679"
