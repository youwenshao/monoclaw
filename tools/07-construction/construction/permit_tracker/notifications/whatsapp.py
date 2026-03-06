"""WhatsApp status alert notifications via Twilio."""

from __future__ import annotations

import logging
import time
from typing import Any

logger = logging.getLogger("openclaw.construction.permit_tracker.notifications.whatsapp")

_last_send_ts: float = 0.0


async def send_status_alert(
    config: dict[str, Any],
    submission: dict,
    old_status: str,
    new_status: str,
) -> bool:
    """Send a WhatsApp notification about a submission status change.

    Args:
        config: Notification config with Twilio credentials and recipient.
        submission: The submission dict.
        old_status: Previous status string.
        new_status: New status string.

    Returns:
        True on success, False otherwise.
    """
    bd_ref = submission.get("bd_reference", f"#{submission.get('id', '?')}")
    sub_type = submission.get("submission_type", "GBP")
    project_name = submission.get("project_name", "")

    text = _format_alert_message(bd_ref, sub_type, project_name, old_status, new_status)
    to = config.get("whatsapp_recipient", "")
    if not to:
        logger.warning("No WhatsApp recipient configured — skipping alert")
        return False

    return await _send_whatsapp_message(to, text, config)


def _format_alert_message(
    bd_ref: str,
    sub_type: str,
    project_name: str,
    old_status: str,
    new_status: str,
) -> str:
    lines = [
        f"🏗️ *BD Permit Status Update*",
        f"",
        f"*Reference:* {bd_ref}",
        f"*Type:* {sub_type}",
    ]
    if project_name:
        lines.append(f"*Project:* {project_name}")
    lines.extend([
        f"",
        f"*Status:* {old_status} → *{new_status}*",
    ])

    if new_status in ("Rejected", "Returned for Amendment", "Query Raised"):
        lines.extend([
            f"",
            f"⚠️ _Action required — please review on the BD portal._",
        ])
    elif new_status in ("Approved", "Consent Issued"):
        lines.extend([
            f"",
            f"✅ _Submission approved. Proceed to next stage._",
        ])

    return "\n".join(lines)


async def _send_whatsapp_message(
    to: str,
    text: str,
    config: dict[str, Any],
) -> bool:
    global _last_send_ts

    account_sid = config.get("twilio_account_sid", "")
    auth_token = config.get("twilio_auth_token", "")
    from_number = config.get("twilio_whatsapp_from", "")

    if not all([account_sid, auth_token, from_number]):
        logger.warning("Twilio WhatsApp not configured — skipping send to %s", to)
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
                logger.info("WhatsApp alert sent to %s (sid=%s)", to, resp.json().get("sid"))
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
