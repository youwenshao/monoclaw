"""Twilio webhook handler for WhatsApp booking messages."""

from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import Any

from openclaw_shared.database import get_db
from openclaw_shared.mona_events import emit_event

logger = logging.getLogger("openclaw.table_master.channels.whatsapp")

HK_PHONE_RE = re.compile(r"^\+852[5679]\d{7}$")


def normalise_phone(raw: str) -> str:
    """Strip the ``whatsapp:`` prefix that Twilio adds and return bare E.164."""
    return raw.replace("whatsapp:", "").strip()


async def handle_incoming(
    form_data: dict[str, Any],
    *,
    llm: Any,
    db_path: str,
    mona_db_path: str,
    parse_fn: Any,
    config: Any,
) -> str:
    """Process an incoming Twilio WhatsApp message and return a reply string.

    Parameters
    ----------
    form_data:
        The raw ``request.form()`` dict forwarded by the route.
    llm:
        LLM provider instance (``app.state.llm``).
    db_path:
        Path to the ``table_master.db`` file.
    mona_db_path:
        Path to the ``mona_events.db`` file.
    parse_fn:
        Callable ``async (llm, text) -> dict`` that extracts booking fields.
    config:
        The application config object.
    """
    sender = normalise_phone(form_data.get("From", ""))
    body = (form_data.get("Body", "") or "").strip()

    if not body:
        return ""

    _log_message(db_path, direction="in", phone=sender, text=body)

    parsed = await parse_fn(llm, body)
    language = parsed.get("language", config.messaging.default_language)

    if parsed.get("party_size") and parsed.get("booking_date"):
        reply = _create_booking_from_parsed(
            parsed, sender=sender, db_path=db_path, mona_db_path=mona_db_path,
        )
    else:
        reply = _ask_for_details(language)

    _log_message(db_path, direction="out", phone=sender, text=reply)
    return reply


def _create_booking_from_parsed(
    parsed: dict[str, Any],
    *,
    sender: str,
    db_path: str,
    mona_db_path: str,
) -> str:
    guest_name = parsed.get("guest_name") or sender
    party_size = parsed["party_size"]
    booking_date = parsed["booking_date"]
    booking_time = parsed.get("booking_time", "19:00")
    special = parsed.get("special_requests", "")
    language = parsed.get("language", "zh")

    with get_db(db_path) as conn:
        cursor = conn.execute(
            """INSERT INTO bookings
               (guest_name, guest_phone, party_size, booking_date, booking_time,
                channel, status, special_requests, language_pref)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (guest_name, sender, party_size, booking_date, booking_time,
             "whatsapp", "pending", special, language),
        )
        booking_id = cursor.lastrowid

    emit_event(
        mona_db_path,
        event_type="action_completed",
        tool_name="table-master",
        summary=f"WhatsApp booking #{booking_id} from {guest_name} ({party_size}pax)",
    )

    if language == "zh":
        return (
            f"多謝你嘅預約！\n"
            f"📋 預約編號：#{booking_id}\n"
            f"👤 {guest_name}（{party_size}位）\n"
            f"📅 {booking_date} {booking_time}\n"
            f"我哋會喺60秒內確認你嘅預約。"
        )
    return (
        f"Thank you for your reservation!\n"
        f"📋 Booking #{booking_id}\n"
        f"👤 {guest_name} ({party_size} pax)\n"
        f"📅 {booking_date} {booking_time}\n"
        f"We will confirm within 60 seconds."
    )


def _ask_for_details(language: str) -> str:
    if language == "zh":
        return (
            "你好！請提供以下資料：\n"
            "1. 幾多位？\n"
            "2. 日期同時間？\n"
            "3. 你嘅姓名？\n"
            "例如：「4位，星期六7點半，陳先生」"
        )
    return (
        "Hello! Please provide:\n"
        "1. Party size\n"
        "2. Date and time\n"
        "3. Your name\n"
        "E.g. '4 people, Saturday 7:30pm, Mr Chan'"
    )


def _log_message(db_path: str, *, direction: str, phone: str, text: str) -> None:
    """Best-effort message logging for audit trail."""
    try:
        with get_db(db_path) as conn:
            tables = [
                r[0] for r in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            ]
            if "message_log" in tables:
                conn.execute(
                    """INSERT INTO message_log (direction, phone, message_text, channel)
                       VALUES (?, ?, ?, 'whatsapp')""",
                    (direction, phone, text),
                )
    except Exception as exc:
        logger.warning("Failed to log WhatsApp message: %s", exc)


def build_confirmation_message(booking: dict[str, Any], language: str = "zh") -> str:
    """Build a bilingual confirmation message for outbound WhatsApp."""
    bid = booking.get("id", "?")
    name = booking.get("guest_name", "")
    size = booking.get("party_size", "")
    bdate = booking.get("booking_date", "")
    btime = booking.get("booking_time", "")
    table = booking.get("table_number", "")

    if language == "zh":
        return (
            f"✅ 預約已確認！\n"
            f"預約編號：#{bid}\n"
            f"姓名：{name}\n"
            f"人數：{size}位\n"
            f"日期：{bdate} {btime}\n"
            f"枱號：{table}\n"
            f"如需更改，請回覆此訊息。"
        )
    return (
        f"✅ Booking confirmed!\n"
        f"Booking #{bid}\n"
        f"Name: {name}\n"
        f"Party: {size} pax\n"
        f"Date: {bdate} {btime}\n"
        f"Table: {table}\n"
        f"Reply to this message to make changes."
    )


def build_cancellation_message(booking: dict[str, Any], language: str = "zh") -> str:
    """Build a bilingual cancellation notice."""
    bid = booking.get("id", "?")
    bdate = booking.get("booking_date", "")
    btime = booking.get("booking_time", "")

    if language == "zh":
        return (
            f"❌ 預約 #{bid}（{bdate} {btime}）已取消。\n"
            f"如有需要，歡迎重新預約。"
        )
    return (
        f"❌ Booking #{bid} ({bdate} {btime}) has been cancelled.\n"
        f"Feel free to book again anytime."
    )
