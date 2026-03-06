"""WhatsApp notification delivery for MPF reminders via Twilio."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def send_via_twilio(
    message: str,
    to_number: str,
    twilio_client: Any,
    from_number: str,
) -> bool:
    """Send a WhatsApp message through the Twilio API.

    Args:
        message: Body text.
        to_number: Recipient in ``whatsapp:+852XXXXXXXX`` format.
        twilio_client: An initialised ``twilio.rest.Client`` instance.
        from_number: Sender in ``whatsapp:+1XXXXXXXXXX`` format.

    Returns:
        True on success, False on failure.
    """
    try:
        twilio_client.messages.create(
            body=message,
            from_=from_number,
            to=to_number,
        )
        return True
    except Exception:
        logger.exception("Failed to send WhatsApp message to %s", to_number)
        return False


def send_mpf_reminder(
    config: dict[str, Any],
    reminder_message: str,
) -> bool:
    """Send an MPF deadline reminder via WhatsApp.

    ``config`` must contain ``twilio_account_sid``, ``twilio_auth_token``,
    ``twilio_whatsapp_from``, and ``owner_whatsapp``.
    """
    sid = config.get("twilio_account_sid", "")
    token = config.get("twilio_auth_token", "")
    from_number = config.get("twilio_whatsapp_from", "")
    to_number = config.get("owner_whatsapp", "")

    if not all([sid, token, from_number, to_number]):
        logger.warning("WhatsApp not configured — skipping MPF reminder")
        return False

    try:
        from twilio.rest import Client  # type: ignore[import-untyped]

        client = Client(sid, token)
    except ImportError:
        logger.warning("twilio package not installed — skipping MPF reminder")
        return False

    return send_via_twilio(reminder_message, to_number, client, from_number)
