"""Partner escalation logic for overdue or at-risk filings."""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from openclaw_shared.database import get_db

logger = logging.getLogger("openclaw.accounting.tax_calendar.escalation")


def check_escalations(db_path: str | Path, config: dict) -> list[dict[str, Any]]:
    """Identify deadlines that need partner escalation and send notifications.

    Escalation triggers when:
    1. Filing is not submitted AND
    2. The due date is within `escalation_days` of today (or already past) AND
    3. The reminder has not already been escalated
    """
    escalation_days = config.get("extra", {}).get("escalation_days", 7)
    threshold_date = (date.today() + timedelta(days=escalation_days)).isoformat()
    today = date.today().isoformat()
    escalated: list[dict[str, Any]] = []

    with get_db(db_path) as conn:
        rows = conn.execute(
            """SELECT d.*, c.company_name, c.partner, c.partner_phone,
                      c.assigned_accountant, c.accountant_phone
               FROM deadlines d
               JOIN clients c ON c.id = d.client_id
               WHERE d.filing_status NOT IN ('filed','submitted')
                 AND COALESCE(d.extended_due_date, d.original_due_date) <= ?
                 AND d.id NOT IN (
                     SELECT deadline_id FROM reminders WHERE escalated = 1
                 )""",
            (threshold_date,),
        ).fetchall()

    for row in rows:
        dl = dict(row)
        success = _escalate_to_partner(dl, config)

        if success:
            with get_db(db_path) as conn:
                existing = conn.execute(
                    "SELECT id FROM reminders WHERE deadline_id = ? AND escalated = 1",
                    (dl["id"],),
                ).fetchone()
                if not existing:
                    conn.execute(
                        """INSERT INTO reminders
                           (deadline_id, days_before, scheduled_date, channel, recipient, sent, sent_at, escalated)
                           VALUES (?,?,?,?,?,1,?,1)""",
                        (
                            dl["id"], 0, today, "escalation",
                            dl.get("partner_phone", ""),
                            datetime.now().isoformat(),
                        ),
                    )

            escalated.append(dl)
            logger.warning(
                "Escalated to partner %s: %s %s (due %s)",
                dl.get("partner", "N/A"),
                dl["company_name"],
                dl.get("form_code", ""),
                dl.get("extended_due_date") or dl["original_due_date"],
            )

    return escalated


def _escalate_to_partner(deadline: dict, config: dict) -> bool:
    """Send escalation notification to the assigned partner."""
    partner = deadline.get("partner")
    partner_phone = deadline.get("partner_phone")
    if not partner or not partner_phone:
        logger.warning(
            "No partner info for deadline %d (%s), cannot escalate",
            deadline["id"], deadline.get("company_name", ""),
        )
        return False

    message = _format_escalation_message(deadline)

    try:
        messaging = config.get("messaging", {})

        if messaging.get("whatsapp_enabled"):
            from openclaw_shared.messaging.whatsapp import WhatsAppProvider
            provider = WhatsAppProvider(
                messaging["twilio_account_sid"],
                messaging["twilio_auth_token"],
                messaging["twilio_whatsapp_from"],
            )
            import asyncio
            asyncio.get_event_loop().run_until_complete(provider.send_text(partner_phone, message))
            return True

        if messaging.get("telegram_enabled"):
            from openclaw_shared.messaging.telegram import TelegramProvider
            provider = TelegramProvider(messaging["telegram_bot_token"])
            import asyncio
            asyncio.get_event_loop().run_until_complete(provider.send_text(partner_phone, message))
            return True

        logger.info(
            "Escalation [dry run] → %s (%s): %s",
            partner, partner_phone, message[:100],
        )
        return True

    except Exception:
        logger.exception("Failed to send escalation for deadline %d", deadline["id"])
        return False


def _format_escalation_message(deadline: dict) -> str:
    """Build the partner escalation notification text."""
    company = deadline.get("company_name", "Unknown")
    form = deadline.get("form_code") or deadline.get("deadline_type", "Filing")
    due = deadline.get("extended_due_date") or deadline["original_due_date"]
    accountant = deadline.get("assigned_accountant", "Unassigned")
    status = deadline.get("filing_status", "unknown")

    effective_due = date.fromisoformat(due) if isinstance(due, str) else due
    days_overdue = (date.today() - effective_due).days

    if days_overdue > 0:
        urgency = f"⚠️ OVERDUE by {days_overdue} day(s)"
    else:
        urgency = f"⚡ Due in {abs(days_overdue)} day(s)"

    return (
        f"🚨 ESCALATION: Filing at risk\n"
        f"{urgency}\n"
        f"Company: {company}\n"
        f"Form: {form}\n"
        f"Due date: {due}\n"
        f"Current status: {status}\n"
        f"Assigned to: {accountant}\n"
        f"Please review and take action immediately."
    )
