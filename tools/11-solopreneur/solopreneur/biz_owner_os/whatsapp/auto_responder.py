"""Keyword-based auto-responder with bilingual (EN/TC) support.

Matches inbound messages against known keyword routes before falling
back to an LLM for conversational replies.
"""

from __future__ import annotations

from typing import Any

KEYWORD_ROUTES: dict[str, dict[str, str]] = {
    "hours": {
        "en": "Our business hours are Monday–Saturday, 10:00 AM – 8:00 PM. We are closed on Sundays and public holidays.",
        "tc": "我們的營業時間為星期一至六，上午10時至晚上8時。星期日及公眾假期休息。",
    },
    "營業時間": {
        "en": "Our business hours are Monday–Saturday, 10:00 AM – 8:00 PM. Closed on Sundays and public holidays.",
        "tc": "我們的營業時間為星期一至六，上午10時至晚上8時。星期日及公眾假期休息。",
    },
    "menu": {
        "en": "Please check our latest menu at our website or visit us in-store. Would you like to make a reservation?",
        "tc": "請瀏覽我們的網站查看最新菜單，或親臨店舖。需要預約嗎？",
    },
    "菜單": {
        "en": "Please check our latest menu at our website or visit us in-store.",
        "tc": "請瀏覽我們的網站查看最新菜單，或親臨店舖。需要預約嗎？",
    },
    "pricing": {
        "en": "For our latest pricing, please visit our website or contact us during business hours. We're happy to provide a quote!",
        "tc": "如需最新價目，請瀏覽我們的網站或於營業時間聯絡我們。我們樂意為您報價！",
    },
    "價錢": {
        "en": "For our latest pricing, please visit our website or contact us during business hours.",
        "tc": "如需最新價目，請瀏覽我們的網站或於營業時間聯絡我們。我們樂意為您報價！",
    },
    "price": {
        "en": "For our latest pricing, please visit our website or contact us during business hours. We're happy to provide a quote!",
        "tc": "如需最新價目，請瀏覽我們的網站或於營業時間聯絡我們。我們樂意為您報價！",
    },
    "book": {
        "en": "To make a booking, please reply with your preferred date and time, and the number of guests.",
        "tc": "如需預約，請回覆您的首選日期、時間及人數。",
    },
    "預約": {
        "en": "To make a booking, please reply with your preferred date and time, and the number of guests.",
        "tc": "如需預約，請回覆您的首選日期、時間及人數。",
    },
    "address": {
        "en": "Please refer to our business card or website for our address. You can also find us on Google Maps!",
        "tc": "請參閱我們的名片或網站查看地址，亦可在 Google Maps 搜尋我們！",
    },
    "地址": {
        "en": "Please refer to our business card or website for our address.",
        "tc": "請參閱我們的名片或網站查看地址，亦可在 Google Maps 搜尋我們！",
    },
}

_FALLBACK_PROMPT = (
    "You are a friendly bilingual (English/Traditional Chinese) customer-service "
    "assistant for a Hong Kong small business. Keep replies concise (under 100 words). "
    "If the customer asks something you cannot answer, politely suggest they contact "
    "us during business hours.\n\nCustomer message: {message}"
)


def _detect_language(text: str) -> str:
    """Heuristic: if more than 30% of chars are CJK, treat as Traditional Chinese."""
    cjk = sum(1 for ch in text if "\u4e00" <= ch <= "\u9fff")
    return "tc" if len(text) > 0 and cjk / len(text) > 0.3 else "en"


def _match_keyword(message_text: str) -> str | None:
    """Return the first matching keyword route key, or None."""
    lower = message_text.strip().lower()
    for keyword in KEYWORD_ROUTES:
        if keyword.lower() in lower:
            return keyword
    return None


async def generate_response(
    message_text: str,
    llm: Any = None,
    language: str | None = None,
) -> str:
    """Produce a reply — keyword match first, then LLM fallback.

    *language* overrides auto-detection when provided (``"en"`` or ``"tc"``).
    """
    lang = language or _detect_language(message_text)

    matched = _match_keyword(message_text)
    if matched:
        return KEYWORD_ROUTES[matched].get(lang, KEYWORD_ROUTES[matched]["en"])

    if llm is not None:
        try:
            prompt = _FALLBACK_PROMPT.format(message=message_text)
            if lang == "tc":
                prompt += "\n\nReply in Traditional Chinese (繁體中文)."
            result = await llm.generate(prompt)
            return result if isinstance(result, str) else str(result)
        except Exception:
            pass

    if lang == "tc":
        return "多謝您的訊息！我們會盡快回覆。如有緊急查詢，請於營業時間致電。"
    return "Thank you for your message! We'll get back to you shortly. For urgent enquiries, please call during business hours."
