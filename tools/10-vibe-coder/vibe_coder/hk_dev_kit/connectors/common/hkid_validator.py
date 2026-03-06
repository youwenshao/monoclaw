"""Hong Kong Identity Card (HKID) check-digit validation.

The HKID format is: X123456(C) or XY123456(C)
- 1 or 2 letter prefix (A-Z)
- 6 digits
- 1 check digit (0-9 or A)

Algorithm:
  For a single-letter prefix like A123456(C):
    Treat it as space + A + 1 + 2 + 3 + 4 + 5 + 6
    where space = 36.
    Weights: 9, 8, 7, 6, 5, 4, 3, 2
    Letters are converted to their numeric value: A=10, B=11, ..., Z=35
    Space (padding for single-letter prefix) = 36

  For a double-letter prefix like AB123456(C):
    Weights: 9, 8, 7, 6, 5, 4, 3, 2
    First letter × 9 + second letter × 8 + digits weighted 7..2

  Checksum = sum mod 11
    If remainder == 0 → check digit is '0'
    If remainder == 1 → check digit is 'A'
    Otherwise → check digit is str(11 - remainder)
"""

from __future__ import annotations

import re

_HKID_PATTERN = re.compile(
    r"^([A-Z]{1,2})(\d{6})\(?([0-9A])\)?$",
    re.IGNORECASE,
)


def _letter_value(ch: str) -> int:
    """A=10, B=11, ..., Z=35."""
    return ord(ch.upper()) - ord("A") + 10


def validate_hkid(hkid: str) -> bool:
    """Validate a Hong Kong Identity Card number including the check digit.

    Accepts formats: A123456(7), AB123456(7), A1234567, AB1234567
    (with or without parentheses around the check digit).
    """
    cleaned = hkid.strip().upper().replace(" ", "")
    match = _HKID_PATTERN.match(cleaned)
    if not match:
        return False

    prefix = match.group(1)
    digits_str = match.group(2)
    check_char = match.group(3)

    if len(prefix) == 1:
        values = [36, _letter_value(prefix)]
    else:
        values = [_letter_value(prefix[0]), _letter_value(prefix[1])]

    values.extend(int(d) for d in digits_str)

    weights = [9, 8, 7, 6, 5, 4, 3, 2]
    total = sum(v * w for v, w in zip(values, weights))
    remainder = total % 11

    if remainder == 0:
        expected = "0"
    elif remainder == 1:
        expected = "A"
    else:
        expected = str(11 - remainder)

    return check_char == expected
