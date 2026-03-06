"""Milestone notification logic for case status changes."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from immigration.client_portal.status.tracker import get_status_display, get_next_steps

logger = logging.getLogger("openclaw.immigration.bot.milestones")

TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates"


def notify_milestone(app_state: Any, case: dict, new_status: str) -> None:
    """Generate and dispatch a milestone notification to the client.

    Sends via WhatsApp or Telegram depending on the client's contact info.
    This is a fire-and-forget helper called from the status-update route.
    """
    lang = case.get("language_pref", "en")
    text = _build_notification_text(case, new_status, lang)

    phone = case.get("client_phone")
    telegram_id = case.get("client_telegram_id")
    config = app_state.config

    if phone and getattr(config.messaging, "whatsapp_enabled", False):
        _send_whatsapp_async(phone, text, config)

    if telegram_id and getattr(config.messaging, "telegram_enabled", False):
        _send_telegram_async(telegram_id, text, config)

    logger.info(
        "Milestone notification queued for case %s → %s",
        case.get("reference_code"),
        new_status,
    )


def _build_notification_text(case: dict, new_status: str, lang: str) -> str:
    """Build the notification message from template or fallback."""
    template_text = _load_template("status_update", lang)
    status_label = get_status_display(new_status, lang)
    next_steps = get_next_steps(new_status, case.get("scheme", ""), lang)

    if template_text:
        return template_text.format(
            client_name=case.get("client_name", ""),
            case_ref=case.get("reference_code", ""),
            scheme=case.get("scheme", ""),
            status=status_label,
            next_steps=next_steps,
        )

    if lang == "zh":
        return (
            f"親愛的 {case.get('client_name', '')}，\n\n"
            f"您的個案 {case.get('reference_code', '')}（{case.get('scheme', '')}）的狀態已更新：\n"
            f"新狀態：{status_label}\n\n"
            f"{next_steps}\n\n"
            f"如有任何疑問，請隨時聯繫我們。"
        )

    return (
        f"Dear {case.get('client_name', '')},\n\n"
        f"Your case {case.get('reference_code', '')} ({case.get('scheme', '')}) has been updated:\n"
        f"New status: {status_label}\n\n"
        f"{next_steps}\n\n"
        f"Please don't hesitate to contact us if you have any questions."
    )


def _load_template(template_name: str, lang: str) -> str | None:
    """Load a message template from the templates directory."""
    path = TEMPLATE_DIR / lang / f"{template_name}.txt"
    if path.exists():
        return path.read_text(encoding="utf-8")
    return None


def _send_whatsapp_async(phone: str, text: str, config: Any) -> None:
    """Fire-and-forget WhatsApp send (logs errors, never raises)."""
    try:
        import asyncio
        from immigration.client_portal.bot.whatsapp import send_whatsapp_message

        loop = asyncio.get_event_loop()
        if loop.is_running():
            loop.create_task(send_whatsapp_message(
                phone, text,
                {
                    "twilio_account_sid": config.messaging.twilio_account_sid,
                    "twilio_auth_token": config.messaging.twilio_auth_token,
                    "twilio_whatsapp_from": config.messaging.twilio_whatsapp_from,
                },
            ))
        else:
            loop.run_until_complete(send_whatsapp_message(
                phone, text,
                {
                    "twilio_account_sid": config.messaging.twilio_account_sid,
                    "twilio_auth_token": config.messaging.twilio_auth_token,
                    "twilio_whatsapp_from": config.messaging.twilio_whatsapp_from,
                },
            ))
    except Exception:
        logger.exception("Failed to send WhatsApp milestone to %s", phone)


def _send_telegram_async(chat_id: str, text: str, config: Any) -> None:
    """Fire-and-forget Telegram send (logs errors, never raises)."""
    try:
        import asyncio
        from immigration.client_portal.bot.telegram import send_telegram_message

        loop = asyncio.get_event_loop()
        if loop.is_running():
            loop.create_task(send_telegram_message(
                chat_id, text,
                {"telegram_bot_token": config.messaging.telegram_bot_token},
            ))
        else:
            loop.run_until_complete(send_telegram_message(
                chat_id, text,
                {"telegram_bot_token": config.messaging.telegram_bot_token},
            ))
    except Exception:
        logger.exception("Failed to send Telegram milestone to %s", chat_id)
