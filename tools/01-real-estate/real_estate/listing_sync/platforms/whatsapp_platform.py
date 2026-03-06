"""WhatsApp listing broadcaster.

Formats property listings as punchy broadcast messages and sends them
via the shared WhatsApp messaging provider.
"""

from __future__ import annotations

import logging

from openclaw_shared.messaging.whatsapp import WhatsAppProvider

from real_estate.listing_sync.platforms.base import PlatformAdapter

logger = logging.getLogger("listing_sync.platforms.whatsapp")


def _format_price(price_hkd: int | None) -> str:
    if not price_hkd:
        return "Price on request"
    if price_hkd >= 10_000_000:
        return f"HK${price_hkd / 1_000_000:.1f}M"
    if price_hkd >= 1_000_000:
        return f"HK${price_hkd / 1_000_000:.2f}M"
    return f"HK${price_hkd:,}"


def format_listing_message(listing: dict) -> str:
    """Build a punchy WhatsApp broadcast message with property highlights."""
    title = listing.get("title_en") or listing.get("title_zh") or listing.get("reference_code", "New Listing")
    price = _format_price(listing.get("price_hkd"))
    district = listing.get("district", "")
    estate = listing.get("estate", "")
    area = listing.get("saleable_area_sqft")
    bedrooms = listing.get("bedrooms")
    floor = listing.get("floor", "")
    facing = listing.get("facing", "")

    lines = [f"🏠 *{title}*"]

    if district:
        lines.append(f"📍 {district}" + (f" — {estate}" if estate else ""))

    lines.append(f"💰 {price}")

    details = []
    if area:
        lines.append(f"📐 {area:,.0f} sq ft (saleable)")
    if bedrooms:
        details.append(f"{bedrooms} bed")
    if floor:
        details.append(f"Floor {floor}")
    if facing:
        details.append(f"{facing} facing")
    if details:
        lines.append("🔑 " + " · ".join(details))

    desc = listing.get("description_adapted") or listing.get("description_master") or ""
    if desc:
        preview = desc[:120].rstrip()
        if len(desc) > 120:
            preview += "…"
        lines.append(f"\n_{preview}_")

    lines.append("\n📲 Reply for details / viewing")

    return "\n".join(lines)


class WhatsAppPlatformAdapter(PlatformAdapter):
    """Broadcast listings to a WhatsApp contact list."""

    PLATFORM_NAME = "whatsapp"
    MAX_PHOTOS = 10
    IMAGE_SPEC = (1200, 900)

    def __init__(self, provider: WhatsAppProvider, broadcast_numbers: list[str]) -> None:
        self._provider = provider
        self._broadcast_numbers = broadcast_numbers

    async def post_listing(self, listing: dict, images: list[str]) -> str:
        message = format_listing_message(listing)
        sent_count = 0

        for number in self._broadcast_numbers:
            try:
                if images:
                    await self._provider.send_media(number, message, images[:3])
                else:
                    await self._provider.send_text(number, message)
                sent_count += 1
            except Exception:
                logger.exception("Failed to send listing to %s", number)

        broadcast_id = f"wa-broadcast-{listing.get('id', 'unknown')}"
        logger.info("Broadcast listing to %d/%d contacts: %s", sent_count, len(self._broadcast_numbers), broadcast_id)
        return broadcast_id

    async def update_listing(self, platform_id: str, listing: dict) -> bool:
        message = "📝 *Listing Update*\n" + format_listing_message(listing)
        for number in self._broadcast_numbers:
            try:
                await self._provider.send_text(number, message)
            except Exception:
                logger.exception("Failed to send update to %s", number)
        return True

    async def remove_listing(self, platform_id: str) -> bool:
        logger.info("WhatsApp broadcast %s marked as removed (no recall possible)", platform_id)
        return True

    async def get_stats(self, platform_id: str) -> dict:
        return {
            "platform": self.PLATFORM_NAME,
            "platform_id": platform_id,
            "broadcast_recipients": len(self._broadcast_numbers),
            "views": 0,
            "inquiries": 0,
        }
