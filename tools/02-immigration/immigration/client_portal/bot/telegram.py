"""Telegram Bot handler for the ClientPortal Bot."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger("openclaw.immigration.bot.telegram")


def parse_telegram_update(data: dict) -> dict:
    """Extract relevant fields from a Telegram Bot API update payload.

    Returns a dict with keys: chat_id, text, from_user, message_id.
    """
    message = data.get("message") or data.get("edited_message") or {}
    chat = message.get("chat", {})
    from_user = message.get("from", {})

    return {
        "chat_id": str(chat.get("id", "")),
        "text": message.get("text", "").strip(),
        "from_user": {
            "id": from_user.get("id"),
            "first_name": from_user.get("first_name", ""),
            "last_name": from_user.get("last_name", ""),
            "username": from_user.get("username", ""),
            "language_code": from_user.get("language_code", "en"),
        },
        "message_id": message.get("message_id"),
        "update_id": data.get("update_id"),
    }


async def send_telegram_message(
    chat_id: str,
    text: str,
    config: dict[str, Any],
) -> bool:
    """Send a text message via the Telegram Bot API.

    Returns True on success, False on failure.
    """
    bot_token = config.get("telegram_bot_token", "")
    if not bot_token:
        logger.warning("Telegram bot not configured — skipping send to chat %s", chat_id)
        return False

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"

    try:
        import httpx

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                url,
                json={
                    "chat_id": chat_id,
                    "text": text[:4096],
                    "parse_mode": "HTML",
                },
            )

            if resp.status_code == 200 and resp.json().get("ok"):
                logger.info("Telegram message sent to chat %s", chat_id)
                return True

            logger.error(
                "Telegram API error %d: %s",
                resp.status_code,
                resp.text[:300],
            )
            return False

    except ImportError:
        logger.error("httpx not installed — cannot send Telegram messages")
        return False
    except Exception:
        logger.exception("Failed to send Telegram message to chat %s", chat_id)
        return False
