"""Bilingual WhatsApp message templates for viewing coordination."""

from __future__ import annotations

from datetime import datetime
from typing import Any

TEMPLATES: dict[str, dict[str, str]] = {
    "confirmation": {
        "en": (
            "✅ Viewing Confirmed\n\n"
            "Property: {property_ref}\n"
            "Address: {property_address}\n"
            "Date/Time: {datetime}\n"
            "Viewer: {viewer_name} ({party_size} pax)\n\n"
            "Please arrive 5 minutes early. "
            "Reply CANCEL to cancel or RESCHEDULE to change time."
        ),
        "zh": (
            "✅ 睇樓確認\n\n"
            "物業：{property_ref}\n"
            "地址：{property_address}\n"
            "日期/時間：{datetime}\n"
            "睇樓人：{viewer_name}（{party_size}位）\n\n"
            "請提早5分鐘到達。"
            "回覆「取消」可取消，回覆「改期」可更改時間。"
        ),
    },
    "reminder_24h": {
        "en": (
            "⏰ Reminder: You have a viewing tomorrow\n\n"
            "Property: {property_ref}\n"
            "Address: {property_address}\n"
            "Time: {datetime}\n\n"
            "Reply CONFIRM to confirm or CANCEL to cancel."
        ),
        "zh": (
            "⏰ 提醒：你聽日有睇樓\n\n"
            "物業：{property_ref}\n"
            "地址：{property_address}\n"
            "時間：{datetime}\n\n"
            "回覆「確認」或「取消」。"
        ),
    },
    "reminder_2h": {
        "en": (
            "🔔 Your viewing is in 2 hours!\n\n"
            "Property: {property_ref} — {property_address}\n"
            "Time: {datetime}\n\n"
            "See you soon!"
        ),
        "zh": (
            "🔔 你嘅睇樓安排仲有2個鐘！\n\n"
            "物業：{property_ref} — {property_address}\n"
            "時間：{datetime}\n\n"
            "到時見！"
        ),
    },
    "follow_up": {
        "en": (
            "Hi {viewer_name}, thanks for viewing {property_ref} today!\n\n"
            "Would you like to:\n"
            "1️⃣ Make an offer\n"
            "2️⃣ View again\n"
            "3️⃣ See similar properties\n"
            "4️⃣ No further interest\n\n"
            "Reply with a number or message."
        ),
        "zh": (
            "{viewer_name}你好，多謝你今日睇咗 {property_ref}！\n\n"
            "你想：\n"
            "1️⃣ 出offer\n"
            "2️⃣ 再睇多次\n"
            "3️⃣ 睇類似物業\n"
            "4️⃣ 暫時唔考慮\n\n"
            "回覆數字或訊息。"
        ),
    },
    "cancellation": {
        "en": (
            "❌ Viewing Cancelled\n\n"
            "Property: {property_ref}\n"
            "Original time: {datetime}\n"
            "Reason: {reason}\n\n"
            "Reply BOOK to schedule a new viewing."
        ),
        "zh": (
            "❌ 睇樓已取消\n\n"
            "物業：{property_ref}\n"
            "原定時間：{datetime}\n"
            "原因：{reason}\n\n"
            "回覆「預約」可重新安排。"
        ),
    },
    "reschedule": {
        "en": (
            "🔄 Reschedule Proposal\n\n"
            "Property: {property_ref}\n"
            "Old time: {old_datetime}\n"
            "New proposed time: {new_datetime}\n\n"
            "Reply CONFIRM to accept or suggest another time."
        ),
        "zh": (
            "🔄 改期建議\n\n"
            "物業：{property_ref}\n"
            "原定時間：{old_datetime}\n"
            "建議新時間：{new_datetime}\n\n"
            "回覆「確認」接受，或建議其他時間。"
        ),
    },
}


def _format_datetime(dt_value: Any) -> str:
    """Convert datetime or ISO string to a human-readable HK format."""
    if isinstance(dt_value, str):
        try:
            dt_value = datetime.fromisoformat(dt_value)
        except ValueError:
            return dt_value
    if isinstance(dt_value, datetime):
        return dt_value.strftime("%Y-%m-%d %H:%M (%a)")
    return str(dt_value)


def render_message(template_name: str, context: dict[str, Any], language: str = "en") -> str:
    """Render a named template with the given context dict.

    Falls back to English if the requested language is unavailable.
    """
    templates = TEMPLATES.get(template_name)
    if not templates:
        raise ValueError(f"Unknown template: {template_name}")

    lang = language if language in templates else "en"
    template_str = templates[lang]

    fmt_context = dict(context)
    for key in ("datetime", "old_datetime", "new_datetime"):
        if key in fmt_context:
            fmt_context[key] = _format_datetime(fmt_context[key])

    fmt_context.setdefault("reason", "N/A")
    fmt_context.setdefault("viewer_name", "")
    fmt_context.setdefault("party_size", "1")
    fmt_context.setdefault("property_ref", "")
    fmt_context.setdefault("property_address", "")

    return template_str.format_map(fmt_context)
