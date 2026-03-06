"""LLM-based extraction of booking details from free-text messages.

Supports both Cantonese (粵語) and English input.  Examples of Cantonese
booking requests the parser can handle:

- "4位，星期六7點半"
- "聽日lunch 2個人"
- "6位 下星期五晚7點 要靠窗"
- "Saturday 7:30pm, 4 people, window seat please"
"""

from __future__ import annotations

import json
import logging
import re
from datetime import date, datetime, timedelta
from typing import Any

logger = logging.getLogger("openclaw.table_master.booking.parser")

SYSTEM_PROMPT = """\
You are a restaurant booking assistant that extracts structured reservation \
details from free-text messages in Cantonese or English.

Today is {today} ({weekday}).

Return ONLY a JSON object with these keys (use null for missing fields):
- guest_name: string or null
- party_size: integer or null
- booking_date: "YYYY-MM-DD" or null
- booking_time: "HH:MM" (24-hour) or null
- special_requests: string or null
- language: "zh" or "en"

Rules:
- "聽日" / "tomorrow" → tomorrow's date
- "後日" / "day after tomorrow" → +2 days
- "星期X" / "下星期X" → resolve to the next occurrence
- "今晚" → today's date
- Time words: "7點半" → "19:30", "lunch" → "12:30", "dinner" → "19:00"
- "X位" / "X個人" / "X people" → party_size = X
- "靠窗" → special_requests includes "window seat"
- "安靜" / "quiet" → special_requests includes "quiet"
- "包廂" / "private room" → special_requests includes "private room"
- "卡座" / "booth" → special_requests includes "booth"
- If the message is primarily Chinese characters, language = "zh"
"""

WEEKDAY_ZH = {"一": 0, "二": 1, "三": 2, "四": 3, "五": 4, "六": 5, "日": 6, "天": 6}
WEEKDAY_EN = {
    "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
    "friday": 4, "saturday": 5, "sunday": 6,
    "mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6,
}


async def parse_booking_text(llm: Any, text: str) -> dict[str, Any]:
    """Parse a free-text booking message into structured data.

    Parameters
    ----------
    llm:
        An ``LLMProvider`` instance with an ``async generate()`` method.
    text:
        The raw message from the guest.

    Returns
    -------
    dict with keys: guest_name, party_size, booking_date, booking_time,
    special_requests, language.  Missing fields are ``None``.
    """
    today = date.today()
    weekday = today.strftime("%A")

    result: dict[str, Any] = {
        "guest_name": None,
        "party_size": None,
        "booking_date": None,
        "booking_time": None,
        "special_requests": None,
        "language": _detect_language(text),
    }

    hints = _extract_hints(text, today)
    for k, v in hints.items():
        if v is not None:
            result[k] = v

    system = SYSTEM_PROMPT.format(today=today.isoformat(), weekday=weekday)
    hint_str = json.dumps({k: v for k, v in hints.items() if v is not None}, ensure_ascii=False)
    prompt = (
        f"Parser pre-extracted hints: {hint_str}\n\n"
        f"Extract booking details from this message:\n\n"
        f'"""\n{text}\n"""'
    )

    try:
        raw = await llm.generate(prompt, system=system, temperature=0.1, max_tokens=256)
        parsed = _extract_json(raw)
        if parsed:
            for key in result:
                if parsed.get(key) is not None:
                    result[key] = parsed[key]
    except Exception as exc:
        logger.warning("LLM parsing failed, using regex fallback: %s", exc)

    if result["party_size"] is not None:
        try:
            result["party_size"] = int(result["party_size"])
        except (ValueError, TypeError):
            result["party_size"] = None

    return result


def _detect_language(text: str) -> str:
    cjk_count = sum(1 for c in text if "\u4e00" <= c <= "\u9fff")
    return "zh" if cjk_count > len(text) * 0.15 else "en"


def _extract_hints(text: str, today: date) -> dict[str, Any]:
    """Regex-based pre-extraction to augment LLM accuracy."""
    hints: dict[str, Any] = {}

    party = re.search(r"(\d{1,2})\s*(?:位|個人|people|pax|persons?|guests?)", text, re.IGNORECASE)
    if party:
        hints["party_size"] = int(party.group(1))

    if re.search(r"聽日|明天|tomorrow", text, re.IGNORECASE):
        hints["booking_date"] = (today + timedelta(days=1)).isoformat()
    elif re.search(r"後日|后天|day after tomorrow", text, re.IGNORECASE):
        hints["booking_date"] = (today + timedelta(days=2)).isoformat()
    elif re.search(r"今[日天晚]|today|tonight", text, re.IGNORECASE):
        hints["booking_date"] = today.isoformat()
    else:
        next_week = "下" in text or "next" in text.lower()
        for zh_day, idx in WEEKDAY_ZH.items():
            if f"星期{zh_day}" in text or f"禮拜{zh_day}" in text:
                hints["booking_date"] = _next_weekday(today, idx, force_next_week=next_week).isoformat()
                break
        else:
            for en_day, idx in WEEKDAY_EN.items():
                if re.search(rf"\b{en_day}\b", text, re.IGNORECASE):
                    hints["booking_date"] = _next_weekday(today, idx, force_next_week=next_week).isoformat()
                    break

    time_zh = re.search(r"(\d{1,2})點(?:半|(\d{1,2}))?", text)
    if time_zh:
        hour = int(time_zh.group(1))
        if hour < 10:
            hour += 12
        minute = 30 if "半" in time_zh.group(0) else int(time_zh.group(2) or 0)
        hints["booking_time"] = f"{hour:02d}:{minute:02d}"
    else:
        time_en = re.search(r"(\d{1,2}):(\d{2})\s*(?:pm|am)?", text, re.IGNORECASE)
        if time_en:
            hour = int(time_en.group(1))
            minute = int(time_en.group(2))
            if "pm" in text.lower() and hour < 12:
                hour += 12
            hints["booking_time"] = f"{hour:02d}:{minute:02d}"
        elif re.search(r"lunch|午[餐市]", text, re.IGNORECASE):
            hints["booking_time"] = "12:30"
        elif re.search(r"dinner|晚[餐市飯]|今晚", text, re.IGNORECASE):
            hints["booking_time"] = "19:00"
        elif re.search(r"dim\s*sum|飲茶|點心", text, re.IGNORECASE):
            hints["booking_time"] = "10:30"

    specials = []
    if re.search(r"靠窗|window", text, re.IGNORECASE):
        specials.append("window seat")
    if re.search(r"安靜|quiet", text, re.IGNORECASE):
        specials.append("quiet")
    if re.search(r"包廂|private\s*room", text, re.IGNORECASE):
        specials.append("private room")
    if re.search(r"卡座|booth", text, re.IGNORECASE):
        specials.append("booth")
    if re.search(r"蛋糕|cake|birthday|生日", text, re.IGNORECASE):
        specials.append("birthday")
    if re.search(r"高腳椅|bb椅|baby|highchair|high chair", text, re.IGNORECASE):
        specials.append("highchair")
    if specials:
        hints["special_requests"] = ", ".join(specials)

    return hints


def _next_weekday(from_date: date, weekday: int, *, force_next_week: bool = False) -> date:
    """Return the next occurrence of ``weekday`` (0=Mon) from ``from_date``."""
    days_ahead = weekday - from_date.weekday()
    if days_ahead < 0 or (days_ahead == 0 and force_next_week):
        days_ahead += 7
    if force_next_week and days_ahead <= 7:
        days_ahead += 7 if days_ahead <= from_date.weekday() else 0
        if days_ahead < 7:
            days_ahead += 7
    return from_date + timedelta(days=days_ahead)


def _extract_json(raw: str) -> dict[str, Any] | None:
    """Pull the first JSON object out of possibly decorated LLM output."""
    raw = raw.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)

    brace_start = raw.find("{")
    brace_end = raw.rfind("}")
    if brace_start == -1 or brace_end == -1:
        return None

    try:
        return json.loads(raw[brace_start : brace_end + 1])
    except json.JSONDecodeError:
        return None
