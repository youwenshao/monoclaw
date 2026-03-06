"""Twilio WhatsApp webhook handler for the ClientPortal Bot."""

from __future__ import annotations

import logging
import time
from typing import Any

logger = logging.getLogger("openclaw.immigration.bot.whatsapp")

_last_send_ts: float = 0.0


def parse_twilio_webhook(form_data: dict) -> dict:
    """Extract relevant fields from a Twilio WhatsApp webhook payload.

    Returns a dict with keys: from_number, body, media_urls.
    """
    from_number = str(form_data.get("From", ""))
    body = str(form_data.get("Body", "")).strip()

    media_urls: list[str] = []
    num_media = int(form_data.get("NumMedia", 0))
    for i in range(num_media):
        url = form_data.get(f"MediaUrl{i}")
        if url:
            media_urls.append(str(url))

    return {
        "from_number": from_number,
        "body": body,
        "media_urls": media_urls,
        "profile_name": str(form_data.get("ProfileName", "")),
        "message_sid": str(form_data.get("MessageSid", "")),
    }


async def send_whatsapp_message(to: str, text: str, config: dict[str, Any]) -> bool:
    """Send a WhatsApp message via Twilio.

    Enforces ~1 msg/sec rate limit to stay within Twilio guidelines.
    Returns True on success, False on failure.
    """
    global _last_send_ts

    account_sid = config.get("twilio_account_sid", "")
    auth_token = config.get("twilio_auth_token", "")
    from_number = config.get("twilio_whatsapp_from", "")

    if not all([account_sid, auth_token, from_number]):
        logger.warning("WhatsApp not configured — skipping send to %s", to)
        return False

    elapsed = time.monotonic() - _last_send_ts
    if elapsed < 1.0:
        await _async_sleep(1.0 - elapsed)

    try:
        import httpx

        whatsapp_to = to if to.startswith("whatsapp:") else f"whatsapp:{to}"
        whatsapp_from = from_number if from_number.startswith("whatsapp:") else f"whatsapp:{from_number}"

        url = f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json"

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                url,
                auth=(account_sid, auth_token),
                data={
                    "From": whatsapp_from,
                    "To": whatsapp_to,
                    "Body": text[:1600],
                },
            )
            _last_send_ts = time.monotonic()

            if resp.status_code in (200, 201):
                logger.info("WhatsApp sent to %s (sid=%s)", to, resp.json().get("sid"))
                return True

            logger.error("Twilio error %d: %s", resp.status_code, resp.text[:300])
            return False

    except ImportError:
        logger.error("httpx not installed — cannot send WhatsApp messages")
        return False
    except Exception:
        logger.exception("Failed to send WhatsApp to %s", to)
        return False


async def _async_sleep(seconds: float) -> None:
    import asyncio
    await asyncio.sleep(seconds)
