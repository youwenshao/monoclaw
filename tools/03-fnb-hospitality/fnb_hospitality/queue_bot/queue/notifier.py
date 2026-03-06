"""Notification service: WhatsApp primary, SMS fallback (60s timeout).

Sends table-ready alerts and periodic position updates.
Logs all notifications to the notifications table.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from pathlib import Path

from openclaw_shared.database import get_db

logger = logging.getLogger("openclaw.fnb-hospitality.queue-bot.notifier")

WHATSAPP_TIMEOUT_SECONDS = 60
ARRIVAL_WINDOW_MINUTES = 5

MESSAGES = {
    "table_ready": {
        "zh": (
            "🍽️ {restaurant}：{queue_number}號客人，您的餐桌已準備好！"
            "請於{window}分鐘內到達。"
        ),
        "en": (
            "🍽️ {restaurant}: Queue #{queue_number}, your table is ready! "
            "Please arrive within {window} minutes."
        ),
    },
    "position_update": {
        "zh": "📋 排隊更新：您目前排第{position}位，預計等候約{est_wait}分鐘。",
        "en": "📋 Queue update: You are #{position} in line. Estimated wait: ~{est_wait} minutes.",
    },
}


async def _send_with_fallback(
    messaging_provider: object | None,
    phone: str,
    text: str,
) -> tuple[bool, str]:
    """Try WhatsApp with timeout, fall back to SMS. Returns (delivered, channel)."""
    if messaging_provider is None:
        logger.info("No messaging provider configured — logged only: %s", text)
        return False, "log"

    try:
        await asyncio.wait_for(
            messaging_provider.send_text(phone, text),  # type: ignore[union-attr]
            timeout=WHATSAPP_TIMEOUT_SECONDS,
        )
        return True, "whatsapp"
    except (asyncio.TimeoutError, Exception) as exc:
        logger.warning("WhatsApp failed for %s: %s — trying SMS fallback", phone, exc)

    try:
        await messaging_provider.send_text(phone, text)  # type: ignore[union-attr]
        return True, "sms"
    except Exception as sms_exc:
        logger.error("SMS fallback also failed for %s: %s", phone, sms_exc)
        return False, "sms"


def _log_notification(
    db_path: str | Path,
    queue_entry_id: int,
    notif_type: str,
    channel: str,
    delivered: bool,
    message_text: str,
) -> None:
    """Persist a notification record."""
    with get_db(db_path) as conn:
        conn.execute(
            """INSERT INTO notifications
               (queue_entry_id, type, channel, sent_at, delivered, message_text)
               VALUES (?,?,?,?,?,?)""",
            (queue_entry_id, notif_type, channel,
             datetime.now().isoformat(), delivered, message_text),
        )


async def send_table_ready(
    messaging_provider: object | None,
    phone: str,
    queue_number: int,
    language: str = "zh",
    restaurant_name: str = "",
    db_path: str | Path | None = None,
    queue_entry_id: int | None = None,
) -> bool:
    """Send a table-ready notification. Returns True if delivered."""
    lang = language if language in ("zh", "en") else "zh"
    text = MESSAGES["table_ready"][lang].format(
        restaurant=restaurant_name or "餐廳",
        queue_number=queue_number,
        window=ARRIVAL_WINDOW_MINUTES,
    )

    delivered, channel = await _send_with_fallback(messaging_provider, phone, text)

    if db_path and queue_entry_id:
        _log_notification(db_path, queue_entry_id, "table_ready", channel, delivered, text)

    return delivered


async def send_position_update(
    messaging_provider: object | None,
    phone: str,
    position: int,
    est_wait: int,
    language: str = "zh",
    db_path: str | Path | None = None,
    queue_entry_id: int | None = None,
) -> bool:
    """Send a queue position update. Returns True if delivered."""
    lang = language if language in ("zh", "en") else "zh"
    text = MESSAGES["position_update"][lang].format(
        position=position,
        est_wait=est_wait,
    )

    delivered, channel = await _send_with_fallback(messaging_provider, phone, text)

    if db_path and queue_entry_id:
        _log_notification(db_path, queue_entry_id, "position_update", channel, delivered, text)

    return delivered
