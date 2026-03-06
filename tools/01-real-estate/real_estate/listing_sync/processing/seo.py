"""SEO keyword extraction for property listings."""

from __future__ import annotations

import re

HK_DISTRICT_KEYWORDS = {
    "Central", "Admiralty", "Wan Chai", "Causeway Bay", "Happy Valley",
    "Mid-Levels", "The Peak", "Sheung Wan", "Sai Ying Pun", "Kennedy Town",
    "Tsim Sha Tsui", "Mong Kok", "Yau Ma Tei", "Jordan", "Prince Edward",
    "Tai Kok Tsui", "Olympic", "West Kowloon", "Kowloon Tong", "Kowloon City",
    "Sha Tin", "Ma On Shan", "Tai Po", "Tuen Mun", "Yuen Long",
    "Tseung Kwan O", "Sai Kung", "Clear Water Bay", "Discovery Bay",
    "Repulse Bay", "Stanley", "Aberdeen", "Ap Lei Chau", "Pok Fu Lam",
    "Tung Chung", "Lantau",
}

PROPERTY_TYPE_KEYWORDS = {
    "apartment", "flat", "house", "village house", "penthouse", "duplex",
    "studio", "serviced apartment", "townhouse",
}

AMENITY_KEYWORDS = {
    "MTR", "clubhouse", "swimming pool", "gym", "playground", "garden",
    "car park", "parking", "sea view", "mountain view", "city view",
    "harbour view", "balcony", "terrace", "rooftop",
}


def extract_keywords(listing_data: dict) -> list[str]:
    """Extract SEO keywords from listing data for portal optimisation.

    Combines structured fields with NLP-light extraction from the
    description text. Returns de-duplicated keywords ordered by relevance.
    """
    keywords: list[str] = []
    seen: set[str] = set()

    def _add(kw: str) -> None:
        normalised = kw.strip().lower()
        if normalised and normalised not in seen:
            seen.add(normalised)
            keywords.append(kw.strip())

    if district := listing_data.get("district"):
        _add(district)
        _add(f"{district} property")
        _add(f"{district} apartment for sale")

    if estate := listing_data.get("estate"):
        _add(estate)
        _add(f"{estate} for sale")

    if beds := listing_data.get("bedrooms"):
        _add(f"{beds} bedroom")
        _add(f"{beds} bed apartment")
        if beds >= 3:
            _add("family apartment")

    if listing_data.get("saleable_area_sqft"):
        sa = listing_data["saleable_area_sqft"]
        if sa < 400:
            _add("compact apartment")
        elif sa > 1000:
            _add("spacious apartment")
            _add("luxury apartment")

    if price := listing_data.get("price_hkd"):
        if price < 8_000_000:
            _add("affordable Hong Kong property")
        elif price > 30_000_000:
            _add("luxury Hong Kong property")

    if facing := listing_data.get("facing"):
        _add(f"{facing} facing")

    if floor := listing_data.get("floor"):
        floor_lower = floor.lower()
        if any(h in floor_lower for h in ("high", "top", "penthouse")):
            _add("high floor")
        elif any(l in floor_lower for l in ("low", "ground", "g/f")):
            _add("low floor")

    text = " ".join([
        listing_data.get("description_master", ""),
        listing_data.get("title_en", ""),
        listing_data.get("title_zh", ""),
    ])

    for d in HK_DISTRICT_KEYWORDS:
        if re.search(re.escape(d), text, re.IGNORECASE):
            _add(d)

    for a in AMENITY_KEYWORDS:
        if re.search(re.escape(a), text, re.IGNORECASE):
            _add(a)

    _add("Hong Kong property")
    _add("HK real estate")

    return keywords
