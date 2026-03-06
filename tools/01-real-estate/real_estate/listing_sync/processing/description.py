"""LLM-based listing description rewriting for multi-platform syndication."""

from __future__ import annotations

import logging
import re

from openclaw_shared.llm.base import LLMProvider

logger = logging.getLogger("listing_sync.processing.description")

PLATFORM_PROMPTS: dict[str, str] = {
    "28hse": (
        "你是一位香港地產代理，需要將以下樓盤描述改寫為適合28Hse刊登的中文版本。\n"
        "要求：\n"
        "- 以繁體中文為主，簡潔有力\n"
        "- 突出實用面積、景觀、交通配套\n"
        "- 如有實用面積，必須明確標示（符合《一手住宅物業銷售條例》）\n"
        "- 不超過300字\n"
        "- 不要加入虛假資訊\n\n"
        "樓盤資料：\n{listing_summary}\n\n"
        "原始描述：\n{description}"
    ),
    "squarefoot": (
        "You are a Hong Kong real estate agent. Rewrite the following property listing "
        "for Squarefoot.com.hk.\n"
        "Requirements:\n"
        "- English-first, professional and detailed\n"
        "- Highlight saleable area, views, transport links, nearby amenities\n"
        "- If saleable area is provided, state it clearly (Sale of First-hand Residential "
        "Properties Ordinance compliance)\n"
        "- 200-400 words\n"
        "- Do not fabricate information\n\n"
        "Property details:\n{listing_summary}\n\n"
        "Master description:\n{description}"
    ),
    "whatsapp": (
        "You are a Hong Kong real estate agent. Create a short, punchy one-liner "
        "for a WhatsApp broadcast about this property.\n"
        "Requirements:\n"
        "- Maximum 2 sentences\n"
        "- Include emoji for visual appeal\n"
        "- Mention price, area, district, key selling point\n"
        "- If saleable area is available, use it (not gross area)\n"
        "- Bilingual (English with key Chinese terms) is fine\n\n"
        "Property details:\n{listing_summary}\n\n"
        "Master description:\n{description}"
    ),
}

SYSTEM_PROMPT = (
    "You are an experienced Hong Kong real estate copywriter. "
    "You produce accurate, compliant property descriptions. "
    "Never fabricate features or amenities not mentioned in the source data."
)


def _build_listing_summary(listing_data: dict) -> str:
    """Compile the structured listing fields into a readable summary."""
    parts = []

    if ref := listing_data.get("reference_code"):
        parts.append(f"Ref: {ref}")
    if title_en := listing_data.get("title_en"):
        parts.append(f"Title (EN): {title_en}")
    if title_zh := listing_data.get("title_zh"):
        parts.append(f"Title (ZH): {title_zh}")
    if district := listing_data.get("district"):
        parts.append(f"District: {district}")
    if estate := listing_data.get("estate"):
        parts.append(f"Estate: {estate}")
    if address := listing_data.get("address"):
        parts.append(f"Address: {address}")
    if sa := listing_data.get("saleable_area_sqft"):
        parts.append(f"Saleable area: {sa:,.0f} sq ft")
    if ga := listing_data.get("gross_area_sqft"):
        parts.append(f"Gross area: {ga:,.0f} sq ft")
    if price := listing_data.get("price_hkd"):
        parts.append(f"Price: HK${price:,}")
    if beds := listing_data.get("bedrooms"):
        parts.append(f"Bedrooms: {beds}")
    if baths := listing_data.get("bathrooms"):
        parts.append(f"Bathrooms: {baths}")
    if floor := listing_data.get("floor"):
        parts.append(f"Floor: {floor}")
    if facing := listing_data.get("facing"):
        parts.append(f"Facing: {facing}")

    return "\n".join(parts)


def _check_saleable_area_compliance(description: str, listing_data: dict) -> str:
    """Ensure saleable area is mentioned when available (HK regulatory requirement).

    Under the Sale of First-hand Residential Properties Ordinance, listing
    descriptions should reference saleable area rather than gross area.
    """
    sa = listing_data.get("saleable_area_sqft")
    if not sa:
        return description

    sa_mentioned = bool(
        re.search(r"saleable|實用面積|實用", description, re.IGNORECASE)
        or re.search(rf"{sa:,.0f}", description)
        or re.search(rf"{int(sa)}", description)
    )
    if not sa_mentioned:
        suffix = f"\n\n(Saleable area 實用面積: {sa:,.0f} sq ft)"
        description += suffix
        logger.info("Appended saleable area compliance note")

    return description


async def rewrite_description(
    llm: LLMProvider,
    listing_data: dict,
    platform: str,
) -> str:
    """Rewrite a master description for a specific platform using the LLM.

    Returns the adapted description string.
    """
    template = PLATFORM_PROMPTS.get(platform)
    if not template:
        logger.warning("No prompt template for platform '%s', returning master description", platform)
        return listing_data.get("description_master", "")

    summary = _build_listing_summary(listing_data)
    master_desc = listing_data.get("description_master", "")

    prompt = template.format(listing_summary=summary, description=master_desc)

    max_tokens = 256 if platform == "whatsapp" else 512
    try:
        result = await llm.generate(prompt, system=SYSTEM_PROMPT, max_tokens=max_tokens)
    except Exception:
        logger.exception("LLM rewrite failed for platform '%s'", platform)
        return master_desc

    result = _check_saleable_area_compliance(result.strip(), listing_data)
    return result
