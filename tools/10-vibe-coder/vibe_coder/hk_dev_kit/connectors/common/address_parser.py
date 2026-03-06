"""Hong Kong address parser — extracts structured components from free-text addresses."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

_TERRITORIES = {
    "hong kong island": "Hong Kong Island",
    "hong kong": "Hong Kong Island",
    "hk island": "Hong Kong Island",
    "kowloon": "Kowloon",
    "kln": "Kowloon",
    "new territories": "New Territories",
    "nt": "New Territories",
    "n.t.": "New Territories",
}

_DISTRICTS = [
    "Central and Western", "Eastern", "Southern", "Wan Chai",
    "Kowloon City", "Kwun Tong", "Sham Shui Po", "Wong Tai Sin", "Yau Tsim Mong",
    "Islands", "Kwai Tsing", "North", "Sai Kung", "Sha Tin",
    "Tai Po", "Tsuen Wan", "Tuen Mun", "Yuen Long",
    "Central", "Admiralty", "Sheung Wan", "Causeway Bay", "Tsim Sha Tsui",
    "Mong Kok", "Jordan", "Hung Hom", "Aberdeen", "Stanley",
    "Repulse Bay", "Happy Valley", "North Point", "Quarry Bay",
    "Chai Wan", "Shau Kei Wan", "Taikoo", "Whampoa",
]


@dataclass
class HKAddress:
    territory: str = ""
    district: str = ""
    estate: str = ""
    building: str = ""
    block: str = ""
    floor: str = ""
    unit: str = ""
    street: str = ""


def parse_hk_address(address: str) -> HKAddress:
    """Parse a free-text Hong Kong address into structured components.

    This uses pattern matching and heuristics — it works well for typical
    English-language HK addresses but is not a replacement for the OGCIO
    Address Lookup Service for production geocoding.
    """
    result = HKAddress()
    text = address.strip()
    lower = text.lower()

    # Territory detection
    for key, value in _TERRITORIES.items():
        if key in lower:
            result.territory = value
            break

    # District detection
    for district in _DISTRICTS:
        if district.lower() in lower:
            result.district = district
            break

    # Floor — patterns: "12/F", "12F", "Floor 12", "12th Floor"
    floor_match = re.search(
        r"(?:(\d{1,3})\s*/\s*[Ff])|(?:(\d{1,3})\s*[Ff]\b)|(?:[Ff]loor\s*(\d{1,3}))|(?:(\d{1,3})(?:st|nd|rd|th)\s*[Ff]loor)",
        text,
    )
    if floor_match:
        result.floor = next(g for g in floor_match.groups() if g is not None)

    # Unit — patterns: "Unit A", "Flat 12A", "Room 1205"
    unit_match = re.search(
        r"(?:[Uu]nit|[Ff]lat|[Rr]oom)\s*([A-Za-z0-9]+)",
        text,
    )
    if unit_match:
        result.unit = unit_match.group(1)

    # Block — patterns: "Block A", "Block 3", "Tower 2"
    block_match = re.search(
        r"(?:[Bb]lock|[Tt]ower)\s*([A-Za-z0-9]+)",
        text,
    )
    if block_match:
        result.block = block_match.group(1)

    # Building name — look for common suffixes
    building_match = re.search(
        r"([\w\s]+?(?:Building|Tower|Mansion|Court|House|Plaza|Centre|Center|Garden|Estate|Terrace|Villa)s?)",
        text,
        re.IGNORECASE,
    )
    if building_match:
        result.building = building_match.group(1).strip()

    # Estate name
    estate_match = re.search(
        r"([\w\s]+?(?:Estate|Garden|City|Village|Park)s?)",
        text,
        re.IGNORECASE,
    )
    if estate_match and estate_match.group(1).strip() != result.building:
        result.estate = estate_match.group(1).strip()

    # Street — look for number + street name patterns
    street_match = re.search(
        r"(\d+[-–]?\d*\s+[\w\s]+?(?:Road|Street|Avenue|Lane|Drive|Path|Way|Praya|Terrace|Boulevard|Circuit))",
        text,
        re.IGNORECASE,
    )
    if street_match:
        result.street = street_match.group(1).strip()

    return result
