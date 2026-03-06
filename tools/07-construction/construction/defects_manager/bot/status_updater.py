"""Send WhatsApp notifications when a defect status changes."""

from __future__ import annotations

import logging
from typing import Any

from openclaw_shared.database import get_db

logger = logging.getLogger("openclaw.construction.defects_manager.bot.status_updater")

STATUS_LABELS: dict[str, str] = {
    "reported": "Reported",
    "assessed": "Under Assessment",
    "work_ordered": "Work Ordered",
    "in_progress": "Repair In Progress",
    "completed": "Repair Completed",
    "closed": "Case Closed",
    "referred": "Referred to External Party",
}


def _build_notification(defect: dict, new_status: str) -> str:
    label = STATUS_LABELS.get(new_status, new_status.replace("_", " ").title())
    lines = [
        f"Defect #{defect['id']} — Status Update",
        f"New status: {label}",
        f"Category: {defect.get('category', 'N/A')}",
        f"Location: {defect.get('floor', '?')}F / Unit {defect.get('unit', '?')}",
    ]
    if new_status == "completed":
        lines.append("Your reported defect has been repaired. Please verify and confirm closure.")
    elif new_status == "work_ordered":
        lines.append("A contractor has been assigned. Repair works will begin shortly.")
    elif new_status == "referred":
        lines.append("This defect has been referred to the relevant authority.")
    return "\n".join(lines)


async def notify_status_change(app_state: Any, defect_id: int, new_status: str) -> bool:
    """Send a WhatsApp notification to the original reporter.

    Returns True if the message was sent successfully.
    """
    db_paths = getattr(app_state, "db_paths", {})
    db = db_paths.get("defects_manager")
    if not db:
        logger.warning("No defects_manager db path — cannot send notification")
        return False

    with get_db(db) as conn:
        row = conn.execute("SELECT * FROM defects WHERE id = ?", (defect_id,)).fetchone()
        if not row:
            logger.warning("Defect #%d not found for notification", defect_id)
            return False
        defect = dict(row)

    phone = defect.get("reported_phone", "")
    if not phone:
        logger.info("No phone for defect #%d — skipping notification", defect_id)
        return False

    config = getattr(app_state, "config", {})
    text = _build_notification(defect, new_status)

    from construction.defects_manager.bot.whatsapp_handler import send_whatsapp_message

    ok = await send_whatsapp_message(phone, text, config)
    if ok:
        logger.info("Status notification sent for defect #%d -> %s", defect_id, new_status)
    return ok
