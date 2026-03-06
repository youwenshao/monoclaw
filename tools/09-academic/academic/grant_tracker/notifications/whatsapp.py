"""WhatsApp notification delivery via Twilio."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger("openclaw.academic.grant_tracker.notifications.whatsapp")


def send_whatsapp_reminder(
    to: str,
    message: str,
    twilio_client: Any,
    from_number: str,
) -> bool:
    """Send a WhatsApp reminder message via Twilio.

    Args:
        to: Recipient WhatsApp number in E.164 format (e.g. "whatsapp:+852XXXXXXXX").
        message: The message body to send.
        twilio_client: An initialised ``twilio.rest.Client`` instance.
        from_number: The Twilio WhatsApp sender number (e.g. "whatsapp:+14155238886").

    Returns:
        True if the message was accepted by Twilio, False on error.
    """
    if not to.startswith("whatsapp:"):
        to = f"whatsapp:{to}"
    if not from_number.startswith("whatsapp:"):
        from_number = f"whatsapp:{from_number}"

    try:
        msg = twilio_client.messages.create(
            body=message,
            from_=from_number,
            to=to,
        )
        logger.info("WhatsApp sent to %s (SID: %s)", to, msg.sid)
        return True
    except Exception:
        logger.exception("Failed to send WhatsApp to %s", to)
        return False


def format_whatsapp_deadline(deadline: dict, days_remaining: int) -> str:
    """Format a deadline reminder for WhatsApp delivery.

    Returns a concise message suitable for mobile viewing.
    """
    scheme = deadline.get("scheme_code", "")
    name = deadline.get("scheme_name", "")
    ext_dl = deadline.get("external_deadline", "N/A")
    inst_dl = deadline.get("institutional_deadline")
    url = deadline.get("call_url", "")

    if days_remaining <= 3:
        header = f"*URGENT* {scheme} deadline in {days_remaining} day{'s' if days_remaining != 1 else ''}!"
    elif days_remaining <= 7:
        header = f"*Reminder* {scheme} deadline in {days_remaining} days"
    else:
        header = f"{scheme} deadline in {days_remaining} days"

    parts = [
        header,
        f"*{name}*",
        f"Deadline: {ext_dl}",
    ]

    if inst_dl:
        parts.append(f"Internal: {inst_dl}")

    if url:
        parts.append(url)

    return "\n".join(parts)
