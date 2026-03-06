"""HKID (Hong Kong Identity Card) number validation."""

from __future__ import annotations

import re

_HKID_PATTERN = re.compile(
    r"^([A-Z]{1,2})(\d{6})\(([0-9A])\)$",
    re.IGNORECASE,
)

_CHAR_VALUES = {chr(i): i - 55 for i in range(65, 91)}  # A=10 .. Z=35


def validate_hkid(hkid: str) -> bool:
    """Validate an HKID number including its check digit.

    Accepted format: 1–2 uppercase letters + 6 digits + check digit in
    parentheses. Examples: ``A123456(7)``, ``AB987654(A)``.

    The algorithm multiplies each position by a weight (8 down to 1 for
    single-letter prefixes, 9 down to 1 for two-letter) and verifies
    that the weighted sum mod 11 equals the check digit (where ``A`` = 10).
    """
    hkid = hkid.strip().upper()
    m = _HKID_PATTERN.match(hkid)
    if not m:
        return False

    prefix, digits, check_char = m.group(1), m.group(2), m.group(3)

    values: list[int] = []
    if len(prefix) == 1:
        values.append(36)  # space placeholder weighted at position 9
        values.append(_CHAR_VALUES[prefix[0]])
    else:
        values.append(_CHAR_VALUES[prefix[0]])
        values.append(_CHAR_VALUES[prefix[1]])

    values.extend(int(d) for d in digits)

    weights = list(range(len(values) + 1, 1, -1))  # 9,8,...,2 or 8,7,...,2
    total = sum(v * w for v, w in zip(values, weights))

    check_value = 10 if check_char == "A" else int(check_char)
    remainder = (total + check_value) % 11
    return remainder == 0
