"""Scheduled tasks for monthly statements and overdue checks."""

from __future__ import annotations

import logging
from datetime import date
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def setup_scheduled_tasks(
    scheduler: Any, db_path: str | Path, config: dict[str, Any]
) -> None:
    """Register recurring jobs on an APScheduler-compatible *scheduler*.

    Jobs:
    - Monthly statement generation on the 1st of each month.
    - Weekly overdue-invoice check every Monday.
    """
    scheduler.add_job(
        run_monthly_statements,
        "cron",
        day=1,
        hour=8,
        minute=0,
        args=[db_path, config],
        id="supplier_ledger_monthly_statements",
        replace_existing=True,
    )
    scheduler.add_job(
        run_overdue_check,
        "cron",
        day_of_week="mon",
        hour=9,
        minute=0,
        args=[db_path, config],
        id="supplier_ledger_overdue_check",
        replace_existing=True,
    )
    logger.info("SupplierLedger scheduled tasks registered")


def run_monthly_statements(db_path: str | Path, config: dict[str, Any]) -> None:
    """Generate statements for the previous month for all active contacts."""
    from solopreneur.supplier_ledger.statements.statement_generator import (
        generate_all_statements,
    )

    today = date.today()
    if today.month == 1:
        year, month = today.year - 1, 12
    else:
        year, month = today.year, today.month - 1

    try:
        results = generate_all_statements(db_path, year, month)
        logger.info(
            "Monthly statements generated: %d statements for %d/%d",
            len(results), month, year,
        )
    except Exception:
        logger.exception("Failed to generate monthly statements")


def run_overdue_check(db_path: str | Path, config: dict[str, Any]) -> None:
    """Find overdue receivables and send reminders where configured."""
    from solopreneur.supplier_ledger.reminders.overdue_alerter import (
        get_overdue_receivables,
        send_payment_reminder,
    )

    threshold = config.get("overdue_threshold_days", 7)
    messaging = config.get("messaging", {})

    try:
        overdue = get_overdue_receivables(db_path, days_overdue_threshold=threshold)
        sent = 0
        for inv in overdue:
            contact = {
                "company_name": inv.get("company_name"),
                "contact_person": inv.get("contact_person"),
                "phone": inv.get("phone"),
                "whatsapp": inv.get("whatsapp"),
                "email": inv.get("email"),
            }
            if send_payment_reminder(inv, contact, messaging):
                sent += 1
        logger.info(
            "Overdue check: %d overdue receivables, %d reminders sent",
            len(overdue), sent,
        )
    except Exception:
        logger.exception("Failed to run overdue check")
