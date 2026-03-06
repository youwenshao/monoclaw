"""LLM-based intent extraction for incoming WhatsApp viewing requests."""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timedelta
from typing import Any

logger = logging.getLogger("openclaw.viewing_bot.parser")

INTENTS = (
    "book_viewing",
    "reschedule",
    "cancel",
    "confirm",
    "check_availability",
    "follow_up",
    "unknown",
)

PARSE_SYSTEM_PROMPT = """\
You are a Hong Kong real estate viewing assistant that extracts structured data
from WhatsApp messages written in English or Chinese (Cantonese/Mandarin).

Return ONLY valid JSON with these fields:
{
  "intent": one of ["book_viewing","reschedule","cancel","confirm","check_availability","follow_up","unknown"],
  "property_ref": string or null (e.g. "TKO-1234", "沙田第一城 3座"),
  "preferred_datetime": ISO-8601 string or null,
  "party_size": integer or null,
  "viewer_name": string or null,
  "notes": string or null
}

Rules:
- Dates like "下星期三" or "next Wed" should resolve relative to today.
- HK phone numbers start with +852 followed by 8 digits (mobile: 5/6/7/9).
- If information is missing, set the field to null.
- Do NOT wrap the JSON in markdown code fences.
"""


def _try_dateparser(text: str) -> str | None:
    """Attempt flexible date parsing with dateparser, returning ISO string."""
    try:
        import dateparser

        dt = dateparser.parse(
            text,
            settings={
                "PREFER_DATES_FROM": "future",
                "TIMEZONE": "Asia/Hong_Kong",
                "RETURN_AS_TIMEZONE_AWARE": False,
            },
        )
        if dt and dt > datetime.now():
            return dt.isoformat()
    except ImportError:
        logger.debug("dateparser not installed; skipping flexible date parse")
    return None


def _extract_datetime_hints(text: str) -> str | None:
    """Pull date/time substrings for the LLM context."""
    iso_match = re.search(r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}", text)
    if iso_match:
        return iso_match.group(0)
    return _try_dateparser(text)


async def parse_viewing_request(llm: Any, message_text: str) -> dict[str, Any]:
    """Use the LLM to extract viewing intent from a natural language message.

    Returns a dict with keys: intent, property_ref, preferred_datetime,
    party_size, viewer_name, notes.
    """
    today = datetime.now().strftime("%Y-%m-%d %A")
    datetime_hint = _extract_datetime_hints(message_text)
    hint_line = f"\nDate hint resolved by parser: {datetime_hint}" if datetime_hint else ""

    prompt = (
        f"Today is {today}.{hint_line}\n\n"
        f"Extract structured viewing request data from this WhatsApp message:\n\n"
        f'"""\n{message_text}\n"""'
    )

    result: dict[str, Any] = {
        "intent": "unknown",
        "property_ref": None,
        "preferred_datetime": None,
        "party_size": None,
        "viewer_name": None,
        "notes": None,
    }

    try:
        raw = await llm.generate(prompt, system=PARSE_SYSTEM_PROMPT, temperature=0.1)
        raw = raw.strip()
        if raw.startswith("```"):
            raw = re.sub(r"^```(?:json)?\s*", "", raw)
            raw = re.sub(r"\s*```$", "", raw)
        parsed = json.loads(raw)

        for key in result:
            if key in parsed and parsed[key] is not None:
                result[key] = parsed[key]

        if result["intent"] not in INTENTS:
            result["intent"] = "unknown"

    except (json.JSONDecodeError, Exception) as exc:
        logger.warning("LLM parse failed (%s), returning fallback form", exc)
        result["notes"] = f"[unparsed] {message_text}"
        result["intent"] = _guess_intent_fallback(message_text)

    return result


def _guess_intent_fallback(text: str) -> str:
    """Keyword-based fallback when LLM parsing fails."""
    lower = text.lower()
    if any(w in lower for w in ("book", "view", "睇樓", "预约", "預約", "看房")):
        return "book_viewing"
    if any(w in lower for w in ("cancel", "取消")):
        return "cancel"
    if any(w in lower for w in ("reschedule", "改期", "改时间", "改時間")):
        return "reschedule"
    if any(w in lower for w in ("confirm", "確認", "确认", "ok", "得")):
        return "confirm"
    if any(w in lower for w in ("available", "有冇", "空", "slot")):
        return "check_availability"
    return "unknown"


def build_fallback_form_response(language: str = "en") -> str:
    """Return a structured form message when LLM parse fails."""
    if language == "zh":
        return (
            "抱歉，我未能理解你嘅訊息。請用以下格式回覆：\n\n"
            "物業編號：\n"
            "希望日期：\n"
            "希望時間：\n"
            "人數：\n"
            "姓名：\n"
        )
    return (
        "Sorry, I couldn't understand your message. "
        "Please reply with the following format:\n\n"
        "Property Ref:\n"
        "Preferred Date:\n"
        "Preferred Time:\n"
        "Party Size:\n"
        "Your Name:\n"
    )
