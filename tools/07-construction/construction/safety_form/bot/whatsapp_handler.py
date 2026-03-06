"""Twilio WhatsApp webhook handler for the SafetyForm Bot."""

from __future__ import annotations

import logging
import time
from datetime import date
from pathlib import Path
from typing import Any

logger = logging.getLogger("openclaw.construction.safety_form.bot.whatsapp")

_last_send_ts: float = 0.0


def parse_twilio_webhook(form_data: dict) -> dict:
    """Extract relevant fields from a Twilio WhatsApp webhook payload."""
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


def _classify_intent(body: str, has_media: bool) -> str:
    """Classify the message intent based on text content and media presence."""
    lower = body.lower().strip()

    incident_keywords = [
        "incident", "accident", "injury", "hurt", "collapse",
        "fire", "fall", "emergency", "danger", "unsafe",
    ]
    if any(kw in lower for kw in incident_keywords):
        return "incident_report"

    checklist_keywords = [
        "pass", "fail", "ok", "yes", "no", "na", "n/a",
        "done", "check", "checked", "good", "bad",
    ]
    if any(kw in lower for kw in checklist_keywords):
        return "checklist_response"

    if has_media and not body:
        return "photo_upload"

    if has_media:
        return "photo_upload"

    return "general"


async def download_media(
    media_url: str,
    workspace: Path,
    site_id: int,
    category: str,
    item_id: int,
    config: dict[str, Any],
) -> str | None:
    """Download media from Twilio and save with structured naming."""
    today = date.today().isoformat()
    dest_dir = workspace / "photos" / str(site_id) / today
    dest_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{category}_{item_id}.jpg"
    dest_path = dest_dir / filename

    account_sid = config.get("twilio_account_sid", "")
    auth_token = config.get("twilio_auth_token", "")

    if not all([account_sid, auth_token]):
        logger.warning("Twilio credentials not configured — cannot download media")
        return None

    try:
        import httpx

        async with httpx.AsyncClient() as client:
            resp = await client.get(media_url, auth=(account_sid, auth_token), follow_redirects=True)
            if resp.status_code == 200:
                dest_path.write_bytes(resp.content)
                logger.info("Media saved to %s", dest_path)
                return str(dest_path)
            logger.error("Media download failed: HTTP %d", resp.status_code)
            return None
    except ImportError:
        logger.error("httpx not installed — cannot download media")
        return None
    except Exception:
        logger.exception("Failed to download media from %s", media_url)
        return None


async def send_whatsapp_message(to: str, text: str, config: dict[str, Any]) -> bool:
    """Send a WhatsApp message via Twilio with rate limiting."""
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


async def handle_incoming(form_data: dict, app_state: Any) -> None:
    """Main entry point for incoming WhatsApp messages (called from routes.py)."""
    parsed = parse_twilio_webhook(form_data)
    sender = parsed["from_number"]
    body = parsed["body"]
    media_urls = parsed["media_urls"]
    has_media = len(media_urls) > 0

    intent = _classify_intent(body, has_media)
    logger.info(
        "Incoming from %s — intent=%s body=%r media=%d",
        sender, intent, body[:80], len(media_urls),
    )

    messaging_cfg = _get_messaging_config(app_state)

    if intent == "incident_report":
        from construction.safety_form.bot.incident_reporter import process_incident_report
        result = await process_incident_report(app_state, form_data)
        await send_whatsapp_message(
            sender,
            f"⚠️ Incident #{result.get('incident_id', '?')} logged. "
            "Project manager notified. Stay safe.",
            messaging_cfg,
        )

    elif intent == "checklist_response":
        from construction.safety_form.bot.checklist_flow import process_checklist_response
        media_url = media_urls[0] if media_urls else None
        result = await process_checklist_response(app_state, sender, body, media_url)
        if result.get("reply"):
            await send_whatsapp_message(sender, result["reply"], messaging_cfg)

    elif intent == "photo_upload":
        if media_urls:
            photo_path = await download_media(
                media_urls[0],
                app_state.workspace,
                site_id=0,
                category="general",
                item_id=int(time.time()),
                config=messaging_cfg,
            )
            reply = "📷 Photo received and saved." if photo_path else "Failed to save photo."
            await send_whatsapp_message(sender, reply, messaging_cfg)

    else:
        await send_whatsapp_message(
            sender,
            "SafetyForm Bot 🏗️\n"
            "Commands:\n"
            "• Send 'checklist' to start daily inspection\n"
            "• Send 'incident' + description to report\n"
            "• Send a photo to attach to current item",
            messaging_cfg,
        )


def _get_messaging_config(app_state: Any) -> dict[str, Any]:
    """Extract messaging config from app_state."""
    config = getattr(app_state, "config", None)
    if config is None:
        return {}
    messaging = getattr(config, "messaging", None)
    if messaging is None:
        return {}
    return {
        "twilio_account_sid": getattr(messaging, "twilio_account_sid", ""),
        "twilio_auth_token": getattr(messaging, "twilio_auth_token", ""),
        "twilio_whatsapp_from": getattr(messaging, "twilio_whatsapp_from", ""),
    }


async def _async_sleep(seconds: float) -> None:
    import asyncio
    await asyncio.sleep(seconds)
