"""WhatsApp Status publisher via Twilio (with manual fallback).

WhatsApp Business API does not natively support Status/Story updates.
This module provides a Twilio-based broadcast approach and flags the
limitation so the solopreneur can manually post via the WhatsApp app.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class WhatsAppStatusPublisher:
    """Publish promotional content via WhatsApp.

    Because WhatsApp Status updates are not available through the Business
    API or Twilio, this publisher sends a broadcast message to opted-in
    contacts as a workaround. A ``manual_fallback`` flag is always returned
    so the dashboard can prompt the user to post the Status manually.
    """

    def __init__(self, twilio_client: Any, from_number: str) -> None:
        self.twilio_client = twilio_client
        self.from_number = from_number

    def publish_status(
        self,
        text: str,
        image_path: str | None = None,
        recipient_numbers: list[str] | None = None,
    ) -> dict[str, Any]:
        """Send a broadcast message as a Status workaround.

        Args:
            text: The status / promotional text.
            image_path: Optional local path to an image (sent as MMS if
                the Twilio account supports it; otherwise text-only).
            recipient_numbers: List of E.164 phone numbers. If ``None``,
                an empty broadcast is recorded with ``manual_fallback=True``.

        Returns:
            Dict with ``sent``, ``failed``, ``manual_fallback``, and per-
            recipient ``details``.
        """
        sent = 0
        failed = 0
        details: list[dict[str, Any]] = []

        if not self.twilio_client or not recipient_numbers:
            logger.info(
                "WhatsApp Status requires manual posting — "
                "Twilio does not support Status API natively."
            )
            return {
                "platform": "whatsapp_status",
                "sent": 0,
                "failed": 0,
                "manual_fallback": True,
                "details": [],
                "hint": (
                    "Please open WhatsApp on your phone and post this "
                    "content as a Status update manually."
                ),
            }

        for number in recipient_numbers:
            to = f"whatsapp:{number}" if not number.startswith("whatsapp:") else number
            from_ = (
                f"whatsapp:{self.from_number}"
                if not self.from_number.startswith("whatsapp:")
                else self.from_number
            )
            try:
                kwargs: dict[str, Any] = {"body": text, "from_": from_, "to": to}
                if image_path:
                    kwargs["media_url"] = [image_path]

                msg = self.twilio_client.messages.create(**kwargs)
                sent += 1
                details.append({"to": number, "sid": msg.sid, "status": "sent"})
            except Exception as exc:
                failed += 1
                details.append({"to": number, "error": str(exc), "status": "failed"})
                logger.warning("WhatsApp send to %s failed: %s", number, exc)

        return {
            "platform": "whatsapp_status",
            "sent": sent,
            "failed": failed,
            "manual_fallback": True,
            "details": details,
            "hint": (
                "Broadcast sent to opted-in contacts. For a true Status "
                "update, please also post manually in WhatsApp."
            ),
        }
