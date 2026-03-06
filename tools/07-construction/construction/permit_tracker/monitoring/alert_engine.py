"""Status change notification engine.

Processes status transitions and dispatches alerts via Mona feed,
WhatsApp, and email based on the severity of the change.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from openclaw_shared.database import get_db
from openclaw_shared.mona_events import emit_event

logger = logging.getLogger("openclaw.construction.permit_tracker.monitoring.alert_engine")

HKT = ZoneInfo("Asia/Hong_Kong")

HIGH_PRIORITY_TRANSITIONS = {
    ("Under Processing", "Approved"),
    ("Under Processing", "Consent Issued"),
    ("Under Processing", "Rejected"),
    ("Under Examination", "Approved"),
    ("Under Examination", "Rejected"),
    ("Under Examination", "Query Raised"),
    ("Received", "Rejected"),
    ("Pending Review", "Rejected"),
}

URGENT_STATUSES = {"Rejected", "Returned for Amendment", "Query Raised"}


async def process_status_change(
    db_path: Any,
    mona_db: Any,
    submission: dict,
    old_status: str,
    new_status: str,
) -> None:
    """Process a status change and dispatch appropriate notifications.

    1. Determines alert severity
    2. Records alert in the database
    3. Emits a Mona feed event
    4. Sends WhatsApp / email if configured
    """
    sub_id = submission["id"]
    bd_ref = submission.get("bd_reference", f"#{sub_id}")
    sub_type = submission.get("submission_type", "GBP")

    severity = _classify_severity(old_status, new_status)
    message = _build_alert_message(bd_ref, sub_type, old_status, new_status, severity)

    logger.info(
        "Processing %s status change for %s: %s -> %s",
        severity, bd_ref, old_status, new_status,
    )

    _record_alert(db_path, sub_id, "status_change", message)

    emit_event(
        mona_db,
        event_type="status_changed" if severity != "urgent" else "alert_triggered",
        tool_name="permit-tracker",
        summary=message,
    )

    await _dispatch_notifications(db_path, submission, old_status, new_status, severity, message)


def _classify_severity(old_status: str, new_status: str) -> str:
    if new_status in URGENT_STATUSES:
        return "urgent"
    if (old_status, new_status) in HIGH_PRIORITY_TRANSITIONS:
        return "high"
    return "normal"


def _build_alert_message(
    bd_ref: str,
    sub_type: str,
    old_status: str,
    new_status: str,
    severity: str,
) -> str:
    prefix = "[URGENT] " if severity == "urgent" else ""
    return (
        f"{prefix}{sub_type} submission {bd_ref}: "
        f"status changed from '{old_status}' to '{new_status}'"
    )


def _record_alert(
    db_path: Any,
    submission_id: int,
    alert_type: str,
    message: str,
) -> int:
    now = datetime.now(HKT).isoformat()
    with get_db(db_path) as conn:
        cursor = conn.execute(
            "INSERT INTO alerts (submission_id, alert_type, message, channel, sent_at) "
            "VALUES (?,?,?,?,?)",
            (submission_id, alert_type, message, "mona", now),
        )
        return cursor.lastrowid  # type: ignore[return-value]


async def _dispatch_notifications(
    db_path: Any,
    submission: dict,
    old_status: str,
    new_status: str,
    severity: str,
    message: str,
) -> None:
    """Send WhatsApp and email notifications for high-priority changes."""
    if severity not in ("urgent", "high"):
        return

    config = _load_notification_config(db_path)
    if not config:
        return

    if config.get("whatsapp_enabled"):
        try:
            from construction.permit_tracker.notifications.whatsapp import send_status_alert
            sent = await send_status_alert(config, submission, old_status, new_status)
            if sent:
                _record_alert(db_path, submission["id"], "status_change", f"[WhatsApp] {message}")
        except Exception:
            logger.exception("WhatsApp notification failed for submission %s", submission.get("id"))

    if config.get("email_enabled"):
        recipients = config.get("email_recipients", [])
        if recipients:
            try:
                from construction.permit_tracker.notifications.email_sender import send_email_alert
                subject = f"BD Permit Status: {submission.get('bd_reference', '')} — {new_status}"
                sent = send_email_alert(config, subject, message, recipients)
                if sent:
                    _record_alert(db_path, submission["id"], "status_change", f"[Email] {message}")
            except Exception:
                logger.exception("Email notification failed for submission %s", submission.get("id"))


def _load_notification_config(db_path: Any) -> dict[str, Any]:
    """Stub that returns notification prefs. In production this would read
    from config or a preferences table."""
    return {}


async def process_overdue_alert(
    db_path: Any,
    mona_db: Any,
    submission: dict,
    days_overdue: int,
) -> None:
    """Create an alert for an overdue submission."""
    sub_id = submission["id"]
    bd_ref = submission.get("bd_reference", f"#{sub_id}")
    message = f"Submission {bd_ref} is {days_overdue} days overdue"

    logger.warning(message)
    _record_alert(db_path, sub_id, "overdue", message)

    emit_event(
        mona_db,
        event_type="alert_triggered",
        tool_name="permit-tracker",
        summary=message,
    )
