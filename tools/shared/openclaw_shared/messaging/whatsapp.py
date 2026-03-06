"""Twilio WhatsApp Business API adapter."""

from __future__ import annotations

import logging

from openclaw_shared.messaging.base import IncomingMessage, MessagingProvider

logger = logging.getLogger("openclaw.messaging.whatsapp")


class WhatsAppProvider(MessagingProvider):
    """Send and receive WhatsApp messages via Twilio."""

    def __init__(self, account_sid: str, auth_token: str, from_number: str) -> None:
        self._from = f"whatsapp:{from_number}"
        try:
            from twilio.rest import Client  # type: ignore[import-untyped]
            self._client = Client(account_sid, auth_token)
        except ImportError:
            raise RuntimeError("twilio is not installed. Install with: pip install twilio")

    async def send_text(self, to: str, text: str) -> str:
        msg = self._client.messages.create(
            body=text,
            from_=self._from,
            to=f"whatsapp:{to}",
        )
        logger.info("WhatsApp text sent to %s: sid=%s", to, msg.sid)
        return msg.sid

    async def send_media(self, to: str, text: str, media_urls: list[str]) -> str:
        msg = self._client.messages.create(
            body=text,
            from_=self._from,
            to=f"whatsapp:{to}",
            media_url=media_urls,
        )
        logger.info("WhatsApp media sent to %s: sid=%s", to, msg.sid)
        return msg.sid

    def parse_webhook(self, data: dict) -> IncomingMessage:
        return IncomingMessage(
            sender=data.get("From", "").replace("whatsapp:", ""),
            text=data.get("Body", ""),
            media_url=data.get("MediaUrl0"),
            media_type=data.get("MediaContentType0"),
            raw=data,
        )
