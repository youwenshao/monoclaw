"""Call-to-action generators for HK solopreneur social posts.

Includes wa.me link builder, FPS link builder, and LLM-powered CTA
suggestions tailored to Hong Kong business patterns.
"""

from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

_CTA_PROMPT = (
    "You are a marketing expert for Hong Kong small businesses. "
    "Suggest a compelling call-to-action for a {business_type} business. "
    "The post content is:\n\n{post_content}\n\n"
    "Return a JSON object with two keys:\n"
    '  "text": the CTA button/link text (under 30 characters),\n'
    '  "link": a suggested link (wa.me, website, or booking URL).\n'
    "Reply ONLY with the JSON."
)


def generate_whatsapp_link(
    phone_number: str,
    message: str | None = None,
) -> str:
    """Build a wa.me deep-link for a HK phone number.

    Accepts numbers in local (8-digit), +852XXXXXXXX, or plain
    852XXXXXXXX formats.
    """
    digits = re.sub(r"[^\d]", "", phone_number)
    if len(digits) == 8:
        digits = f"852{digits}"
    elif not digits.startswith("852") and len(digits) > 8:
        pass  # assume international already

    link = f"https://wa.me/{digits}"
    if message:
        from urllib.parse import quote
        link += f"?text={quote(message)}"
    return link


def generate_fps_link(fps_id: str) -> str:
    """Generate a Faster Payment System (FPS) payment link.

    FPS identifiers can be a phone number, email, or FPS ID.
    The returned link uses the HKMA-standard ``fps://`` scheme that
    many HK banking apps recognise, with a ``https`` fallback.
    """
    clean_id = fps_id.strip()
    return f"https://fps.hk/fps/pay?id={clean_id}"


async def suggest_cta(
    business_type: str,
    post_content: str,
    llm: Any = None,
) -> dict[str, str]:
    """Suggest a CTA (text + link) for a post, optionally via LLM.

    Falls back to common HK solopreneur CTAs when no LLM is available.
    """
    if llm is not None:
        try:
            import json
            prompt = _CTA_PROMPT.format(
                business_type=business_type, post_content=post_content,
            )
            raw = await llm.generate(prompt)
            text = raw if isinstance(raw, str) else str(raw)
            text = text.strip()
            if text.startswith("{"):
                return json.loads(text)
        except Exception as exc:
            logger.warning("LLM CTA suggestion failed: %s", exc)

    defaults: dict[str, dict[str, str]] = {
        "food": {"text": "WhatsApp to Order 📱", "link": ""},
        "beauty": {"text": "Book Now via WhatsApp", "link": ""},
        "retail": {"text": "Shop Now 🛒", "link": ""},
        "fitness": {"text": "Book a Trial Class", "link": ""},
        "services": {"text": "Get a Free Quote", "link": ""},
    }

    bt_lower = business_type.lower()
    for key, cta in defaults.items():
        if key in bt_lower:
            return cta

    return {"text": "DM us to learn more", "link": ""}
