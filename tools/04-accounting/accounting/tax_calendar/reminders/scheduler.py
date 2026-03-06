"""Reminder scheduling engine using APScheduler."""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from openclaw_shared.database import get_db

logger = logging.getLogger("openclaw.accounting.tax_calendar.reminders")


def schedule_reminders(deadline: dict, config: dict, db_path: str | Path) -> list[int]:
    """Create reminder records for a deadline at configured intervals.

    Default intervals: [60, 30, 7] days before due date.
    Each reminder is persisted so the send job can pick them up.
    """
    intervals = config.get("extra", {}).get("reminder_intervals", [60, 30, 7])
    effective_due = deadline.get("extended_due_date") or deadline["original_due_date"]
    if isinstance(effective_due, str):
        effective_due = date.fromisoformat(effective_due)

    channel = _preferred_channel(config)
    recipient = deadline.get("accountant_phone") or deadline.get("assigned_accountant", "")

    reminder_ids: list[int] = []
    with get_db(db_path) as conn:
        for days_before in intervals:
            scheduled = effective_due - timedelta(days=days_before)
            if scheduled < date.today():
                continue

            existing = conn.execute(
                """SELECT id FROM reminders
                   WHERE deadline_id = ? AND days_before = ?""",
                (deadline["id"], days_before),
            ).fetchone()
            if existing:
                continue

            cursor = conn.execute(
                """INSERT INTO reminders
                   (deadline_id, days_before, scheduled_date, channel, recipient)
                   VALUES (?,?,?,?,?)""",
                (deadline["id"], days_before, scheduled.isoformat(), channel, recipient),
            )
            reminder_ids.append(cursor.lastrowid)

    logger.info(
        "Scheduled %d reminders for deadline %s (due %s)",
        len(reminder_ids), deadline["id"], effective_due,
    )
    return reminder_ids


def check_and_send_reminders(db_path: str | Path, config: dict) -> list[dict[str, Any]]:
    """Check for reminders due today (or overdue) and send them.

    Returns a list of sent reminder records for logging.
    """
    today = date.today().isoformat()
    sent_reminders: list[dict[str, Any]] = []

    with get_db(db_path) as conn:
        due_reminders = conn.execute(
            """SELECT r.*, d.form_code, d.deadline_type, d.filing_status,
                      COALESCE(d.extended_due_date, d.original_due_date) AS effective_due,
                      c.company_name, c.assigned_accountant, c.accountant_phone
               FROM reminders r
               JOIN deadlines d ON d.id = r.deadline_id
               JOIN clients c ON c.id = d.client_id
               WHERE r.sent = 0
                 AND r.scheduled_date <= ?
                 AND d.filing_status NOT IN ('filed','submitted')""",
            (today,),
        ).fetchall()

    for row in due_reminders:
        reminder = dict(row)
        success = _send_reminder(reminder, config)

        if success:
            with get_db(db_path) as conn:
                conn.execute(
                    "UPDATE reminders SET sent = 1, sent_at = ? WHERE id = ?",
                    (datetime.now().isoformat(), reminder["id"]),
                )
            reminder["sent"] = True
            sent_reminders.append(reminder)
            logger.info(
                "Sent reminder %d for %s (%s) to %s",
                reminder["id"], reminder["company_name"],
                reminder.get("form_code", ""), reminder.get("recipient", ""),
            )

    return sent_reminders


def _send_reminder(reminder: dict, config: dict) -> bool:
    """Dispatch a single reminder via the configured channel."""
    channel = reminder.get("channel", "whatsapp")
    recipient = reminder.get("recipient") or reminder.get("accountant_phone", "")
    if not recipient:
        logger.warning("No recipient for reminder %d, skipping", reminder["id"])
        return False

    message = _format_reminder_message(reminder)

    try:
        if channel == "whatsapp" and config.get("messaging", {}).get("whatsapp_enabled"):
            from openclaw_shared.messaging.whatsapp import WhatsAppProvider
            msg_cfg = config["messaging"]
            provider = WhatsAppProvider(
                msg_cfg["twilio_account_sid"],
                msg_cfg["twilio_auth_token"],
                msg_cfg["twilio_whatsapp_from"],
            )
            import asyncio
            asyncio.get_event_loop().run_until_complete(provider.send_text(recipient, message))
            return True

        if channel == "telegram" and config.get("messaging", {}).get("telegram_enabled"):
            from openclaw_shared.messaging.telegram import TelegramProvider
            provider = TelegramProvider(config["messaging"]["telegram_bot_token"])
            import asyncio
            asyncio.get_event_loop().run_until_complete(provider.send_text(recipient, message))
            return True

        logger.info("Reminder %d [%s]: %s → %s (dry run)", reminder["id"], channel, recipient, message[:80])
        return True

    except Exception:
        logger.exception("Failed to send reminder %d", reminder["id"])
        return False


def _format_reminder_message(reminder: dict) -> str:
    """Build the reminder text."""
    company = reminder.get("company_name", "Client")
    form = reminder.get("form_code") or reminder.get("deadline_type", "Filing")
    effective_due = reminder.get("effective_due")
    days_before = reminder.get("days_before", 0)

    return (
        f"⏰ Tax Filing Reminder\n"
        f"Company: {company}\n"
        f"Form: {form}\n"
        f"Due date: {effective_due}\n"
        f"Days remaining: {days_before}\n"
        f"Please ensure all documents are prepared."
    )


def _preferred_channel(config: dict) -> str:
    """Determine the preferred messaging channel from config."""
    messaging = config.get("messaging", {})
    if messaging.get("whatsapp_enabled"):
        return "whatsapp"
    if messaging.get("telegram_enabled"):
        return "telegram"
    return "whatsapp"


def setup_scheduler(db_path: str | Path, config: dict) -> Any:
    """Set up APScheduler to run check_and_send_reminders daily.

    Returns the scheduler instance (caller should call scheduler.start()).
    """
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        from apscheduler.triggers.cron import CronTrigger
    except ImportError:
        logger.warning("APScheduler not installed; reminder scheduling disabled")
        return None

    scheduler = BackgroundScheduler()
    scheduler.add_job(
        check_and_send_reminders,
        CronTrigger(hour=9, minute=0),
        args=[db_path, config],
        id="tax_calendar_reminders",
        replace_existing=True,
        name="Daily tax calendar reminder check",
    )

    logger.info("APScheduler configured for daily reminder checks at 09:00")
    return scheduler
