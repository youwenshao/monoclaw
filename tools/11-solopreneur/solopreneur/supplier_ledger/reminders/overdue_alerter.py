"""Overdue-invoice detection and payment reminder dispatch."""

from __future__ import annotations

import logging
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from openclaw_shared.database import get_db

logger = logging.getLogger(__name__)


def get_overdue_receivables(
    db_path: str | Path, days_overdue_threshold: int = 7
) -> list[dict[str, Any]]:
    """Return receivables overdue by at least *days_overdue_threshold* days."""
    cutoff = (date.today() - timedelta(days=days_overdue_threshold)).isoformat()

    with get_db(db_path) as conn:
        rows = conn.execute(
            """SELECT i.*, c.company_name, c.company_name_tc,
                      c.phone, c.whatsapp, c.email, c.contact_person
               FROM invoices i
               LEFT JOIN contacts c ON c.id = i.contact_id
               WHERE i.invoice_type = 'receivable'
                 AND i.due_date <= ?
                 AND i.status NOT IN ('paid', 'written_off')
               ORDER BY i.due_date ASC""",
            (cutoff,),
        ).fetchall()
    return [dict(r) for r in rows]


def format_reminder_message(
    invoice: dict[str, Any],
    contact: dict[str, Any],
    language: str = "en",
) -> str:
    """Build a polite payment-reminder message in English or Traditional Chinese."""
    name = contact.get("company_name") or contact.get("contact_person") or "Customer"
    inv_no = invoice.get("invoice_number") or f"INV-{invoice.get('id', '?')}"
    amount = invoice.get("balance", invoice.get("total_amount", 0))
    due = invoice.get("due_date", "")
    days = 0
    if due:
        try:
            days = (date.today() - date.fromisoformat(due)).days
        except ValueError:
            pass

    if language == "zh":
        return (
            f"{name} 您好，\n\n"
            f"根據我們的記錄，發票 {inv_no} 的款項 HK${amount:,.2f} "
            f"已逾期 {days} 天（到期日：{due}）。\n\n"
            "煩請安排付款。如已付款，請忽略此提醒。\n\n"
            "如有任何疑問，歡迎隨時聯絡我們。謝謝！"
        )

    return (
        f"Dear {name},\n\n"
        f"Our records show that invoice {inv_no} for HK${amount:,.2f} "
        f"is {days} day(s) overdue (due date: {due}).\n\n"
        "We kindly request your earliest settlement. "
        "If payment has already been made, please disregard this reminder.\n\n"
        "Please do not hesitate to contact us with any queries. Thank you!"
    )


def send_payment_reminder(
    invoice: dict[str, Any],
    contact: dict[str, Any],
    messaging_config: dict[str, Any],
) -> bool:
    """Attempt to send a reminder via WhatsApp (Twilio).

    *messaging_config* should include ``twilio_account_sid``,
    ``twilio_auth_token``, and ``twilio_whatsapp_from``.
    Falls back to logging when credentials are missing.
    """
    to_number = contact.get("whatsapp") or contact.get("phone")
    if not to_number:
        logger.warning(
            "No phone/whatsapp for contact %s — skipping reminder",
            contact.get("company_name"),
        )
        return False

    language = messaging_config.get("default_language", "en")
    body = format_reminder_message(invoice, contact, language)

    sid = messaging_config.get("twilio_account_sid")
    token = messaging_config.get("twilio_auth_token")
    from_number = messaging_config.get("twilio_whatsapp_from")

    if not (sid and token and from_number):
        logger.info(
            "Twilio not configured — reminder for %s logged only:\n%s",
            contact.get("company_name"),
            body,
        )
        return False

    try:
        from twilio.rest import Client as TwilioClient  # type: ignore[import-untyped]

        client = TwilioClient(sid, token)
        client.messages.create(
            body=body,
            from_=f"whatsapp:{from_number}",
            to=f"whatsapp:{to_number}",
        )
        logger.info("Payment reminder sent to %s", to_number)
        return True
    except Exception:
        logger.exception("Failed to send reminder to %s", to_number)
        return False
