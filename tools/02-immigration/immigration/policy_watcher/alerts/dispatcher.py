"""Multi-channel alert dispatcher (WhatsApp, Telegram, SMTP)."""

from __future__ import annotations

import logging
import smtplib
from datetime import datetime
from email.message import EmailMessage
from pathlib import Path
from typing import Any

import httpx

from openclaw_shared.database import get_db

logger = logging.getLogger("openclaw.immigration.policy_watcher.alerts.dispatcher")

URGENCY_LABELS = {"routine": "Routine", "important": "Important", "urgent": "URGENT"}


def _format_message(change: dict[str, Any]) -> str:
    urgency = URGENCY_LABELS.get(change.get("urgency", "routine"), "Notice")
    lines = [
        f"[{urgency}] Policy Change Alert",
        "",
        f"Summary: {change.get('change_summary', 'N/A')}",
        f"Affected Schemes: {change.get('affected_schemes', 'N/A')}",
    ]
    if change.get("effective_date"):
        lines.append(f"Effective Date: {change['effective_date']}")
    lines.append("")
    lines.append("— MonoClaw PolicyWatcher")
    return "\n".join(lines)


async def _send_whatsapp(
    phone: str,
    message: str,
    config: dict[str, Any],
) -> dict[str, Any]:
    account_sid = config.get("twilio_account_sid", "")
    auth_token = config.get("twilio_auth_token", "")
    from_number = config.get("twilio_whatsapp_from", "")

    if not all([account_sid, auth_token, from_number]):
        return {"channel": "whatsapp", "status": "skipped", "reason": "not_configured"}

    url = f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json"
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(
                url,
                auth=(account_sid, auth_token),
                data={
                    "From": f"whatsapp:{from_number}",
                    "To": f"whatsapp:{phone}",
                    "Body": message,
                },
                timeout=30,
            )
            resp.raise_for_status()
            return {"channel": "whatsapp", "status": "sent", "sid": resp.json().get("sid")}
        except httpx.HTTPError as exc:
            logger.error("WhatsApp send failed: %s", exc)
            return {"channel": "whatsapp", "status": "failed", "error": str(exc)}


async def _send_telegram(
    chat_id: str,
    message: str,
    config: dict[str, Any],
) -> dict[str, Any]:
    bot_token = config.get("telegram_bot_token", "")
    if not bot_token:
        return {"channel": "telegram", "status": "skipped", "reason": "not_configured"}

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(
                url,
                json={"chat_id": chat_id, "text": message, "parse_mode": "Markdown"},
                timeout=30,
            )
            resp.raise_for_status()
            return {"channel": "telegram", "status": "sent"}
        except httpx.HTTPError as exc:
            logger.error("Telegram send failed: %s", exc)
            return {"channel": "telegram", "status": "failed", "error": str(exc)}


async def _send_email(
    email_addr: str,
    message: str,
    change: dict[str, Any],
    config: dict[str, Any],
) -> dict[str, Any]:
    smtp_host = config.get("smtp_host", "localhost")
    smtp_port = int(config.get("smtp_port", 587))
    smtp_user = config.get("smtp_user", "")
    smtp_pass = config.get("smtp_pass", "")
    from_addr = config.get("smtp_from", smtp_user or "noreply@monoclaw.local")

    if not smtp_user:
        return {"channel": "email", "status": "skipped", "reason": "not_configured"}

    urgency = change.get("urgency", "routine")
    subject = f"[MonoClaw {URGENCY_LABELS.get(urgency, 'Notice')}] Policy Change Alert"

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = from_addr
    msg["To"] = email_addr
    msg.set_content(message)

    try:
        with smtplib.SMTP(smtp_host, smtp_port, timeout=30) as server:
            server.ehlo()
            if smtp_port != 25:
                server.starttls()
            if smtp_user and smtp_pass:
                server.login(smtp_user, smtp_pass)
            server.send_message(msg)
        return {"channel": "email", "status": "sent"}
    except Exception as exc:
        logger.error("Email send failed: %s", exc)
        return {"channel": "email", "status": "failed", "error": str(exc)}


def _log_alert(
    db_path: str | Path,
    change_id: int,
    subscription_id: int,
    channel: str,
    status: str,
) -> None:
    with get_db(db_path) as conn:
        conn.execute(
            """INSERT INTO alert_log (change_id, subscription_id, sent_at, channel, delivery_status)
               VALUES (?,?,?,?,?)""",
            (change_id, subscription_id, datetime.utcnow().isoformat(), channel, status),
        )


async def dispatch_alerts(
    change: dict[str, Any],
    subscriptions: list[dict[str, Any]],
    config: dict[str, Any],
) -> list[dict[str, Any]]:
    """Dispatch alerts to all matching subscriptions via their preferred channel.

    Respects urgency thresholds and logs every delivery attempt.
    """
    message = _format_message(change)
    db_path = config.get("db_path", "")
    messaging_config = config.get("messaging", {})
    results: list[dict[str, Any]] = []

    for sub in subscriptions:
        channel = sub.get("channel", "whatsapp")
        sub_id = sub.get("id", 0)
        change_id = change.get("id", 0)

        if channel == "whatsapp" and sub.get("phone"):
            result = await _send_whatsapp(sub["phone"], message, messaging_config)
        elif channel == "telegram" and sub.get("telegram_id"):
            result = await _send_telegram(sub["telegram_id"], message, messaging_config)
        elif channel == "email" and sub.get("email"):
            result = await _send_email(sub["email"], message, change, messaging_config)
        else:
            result = {"channel": channel, "status": "skipped", "reason": "no_contact_info"}

        result["subscription_id"] = sub_id

        if db_path:
            _log_alert(db_path, change_id, sub_id, channel, result["status"])

        results.append(result)

    sent = sum(1 for r in results if r["status"] == "sent")
    logger.info(
        "Dispatched %d/%d alerts for change %s",
        sent, len(results), change.get("id"),
    )
    return results
