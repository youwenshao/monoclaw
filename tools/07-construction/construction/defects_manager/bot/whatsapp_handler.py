"""Twilio WhatsApp webhook handler for resident defect photo reports."""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger("openclaw.construction.defects_manager.bot.whatsapp")

_last_send_ts: float = 0.0


def parse_twilio_webhook(form_data: dict) -> dict:
    """Extract fields from a Twilio WhatsApp webhook payload."""
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


async def download_media(url: str, dest_dir: Path, config: dict[str, Any]) -> Path | None:
    """Download a Twilio media file and return the local path."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    account_sid = config.get("twilio_account_sid", "")
    auth_token = config.get("twilio_auth_token", "")

    try:
        import httpx

        async with httpx.AsyncClient(follow_redirects=True) as client:
            resp = await client.get(url, auth=(account_sid, auth_token) if account_sid else None)
            if resp.status_code != 200:
                logger.error("Media download failed (%d): %s", resp.status_code, url)
                return None

            content_type = resp.headers.get("content-type", "")
            ext = ".jpg"
            if "png" in content_type:
                ext = ".png"
            elif "pdf" in content_type:
                ext = ".pdf"

            filename = f"defect_{int(time.time())}_{hash(url) & 0xFFFF:04x}{ext}"
            path = dest_dir / filename
            path.write_bytes(resp.content)
            logger.info("Media saved to %s", path)
            return path

    except ImportError:
        logger.error("httpx not installed — cannot download media")
        return None
    except Exception:
        logger.exception("Failed to download media from %s", url)
        return None


async def handle_incoming(form_data: dict, app_state: Any) -> None:
    """Process an incoming WhatsApp message — main webhook entry point.

    Delegates to the report flow for guided defect creation.
    """
    parsed = parse_twilio_webhook(form_data)
    sender = parsed["from_number"]
    body = parsed["body"]
    media_urls = parsed["media_urls"]
    config = getattr(app_state, "config", {})

    workspace: Path = getattr(app_state, "workspace", Path("."))
    photo_dir = workspace / "photos" / "defects"

    media_path: str | None = None
    if media_urls:
        downloaded = await download_media(media_urls[0], photo_dir, config)
        if downloaded:
            media_path = str(downloaded)

    from construction.defects_manager.bot.report_flow import process_report_step

    reply = await process_report_step(app_state, sender, body, media_path)

    if reply.get("message"):
        await send_whatsapp_message(sender, reply["message"], config)


async def send_whatsapp_message(to: str, text: str, config: dict[str, Any]) -> bool:
    """Send a WhatsApp message via Twilio with rate limiting."""
    global _last_send_ts  # noqa: PLW0603

    account_sid = config.get("twilio_account_sid", "")
    auth_token = config.get("twilio_auth_token", "")
    from_number = config.get("twilio_whatsapp_from", "")

    if not all([account_sid, auth_token, from_number]):
        logger.warning("WhatsApp not configured — skipping send to %s", to)
        return False

    elapsed = time.monotonic() - _last_send_ts
    if elapsed < 1.0:
        import asyncio
        await asyncio.sleep(1.0 - elapsed)

    try:
        import httpx

        whatsapp_to = to if to.startswith("whatsapp:") else f"whatsapp:{to}"
        whatsapp_from = from_number if from_number.startswith("whatsapp:") else f"whatsapp:{from_number}"

        url = f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json"
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                url,
                auth=(account_sid, auth_token),
                data={"From": whatsapp_from, "To": whatsapp_to, "Body": text[:1600]},
            )
            _last_send_ts = time.monotonic()

            if resp.status_code in (200, 201):
                logger.info("WhatsApp sent to %s", to)
                return True
            logger.error("Twilio error %d: %s", resp.status_code, resp.text[:300])
            return False

    except ImportError:
        logger.error("httpx not installed — cannot send WhatsApp messages")
        return False
    except Exception:
        logger.exception("Failed to send WhatsApp to %s", to)
        return False
