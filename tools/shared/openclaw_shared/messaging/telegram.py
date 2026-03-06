"""Telegram Bot API adapter."""

from __future__ import annotations

import logging

from openclaw_shared.messaging.base import IncomingMessage, MessagingProvider

logger = logging.getLogger("openclaw.messaging.telegram")


class TelegramProvider(MessagingProvider):
    """Send and receive Telegram messages via python-telegram-bot."""

    def __init__(self, bot_token: str) -> None:
        self._token = bot_token
        try:
            from telegram import Bot  # type: ignore[import-untyped]
            self._bot = Bot(token=bot_token)
        except ImportError:
            raise RuntimeError(
                "python-telegram-bot is not installed. "
                "Install with: pip install python-telegram-bot"
            )

    async def send_text(self, to: str, text: str) -> str:
        msg = await self._bot.send_message(chat_id=to, text=text)
        logger.info("Telegram text sent to %s: msg_id=%s", to, msg.message_id)
        return str(msg.message_id)

    async def send_media(self, to: str, text: str, media_urls: list[str]) -> str:
        # Send text first, then each media URL as a photo
        msg = await self._bot.send_message(chat_id=to, text=text)
        for url in media_urls:
            await self._bot.send_photo(chat_id=to, photo=url)
        return str(msg.message_id)

    def parse_webhook(self, data: dict) -> IncomingMessage:
        message = data.get("message", {})
        return IncomingMessage(
            sender=str(message.get("from", {}).get("id", "")),
            text=message.get("text", ""),
            raw=data,
        )
