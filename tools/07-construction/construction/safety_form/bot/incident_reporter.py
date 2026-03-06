"""Incident reporting via WhatsApp with immediate PM escalation."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from openclaw_shared.database import get_db
from openclaw_shared.mona_events import emit_event

logger = logging.getLogger("openclaw.construction.safety_form.bot.incident")


async def process_incident_report(app_state: Any, form_data: dict) -> dict:
    """Process an incoming incident report from WhatsApp and escalate.

    Returns a dict with 'incident_id' and 'escalated' status.
    """
    from construction.safety_form.bot.whatsapp_handler import (
        parse_twilio_webhook,
        send_whatsapp_message,
        download_media,
        _get_messaging_config,
    )

    parsed = parse_twilio_webhook(form_data)
    sender = parsed["from_number"]
    body = parsed["body"]
    media_urls = parsed["media_urls"]

    incident_type, description = _parse_incident_text(body)

    db_path = app_state.db_paths["safety_form"]
    site_id, pm_phone = _lookup_sender_site(db_path, sender)

    photo_path = None
    if media_urls:
        messaging_cfg = _get_messaging_config(app_state)
        photo_path = await download_media(
            media_urls[0],
            app_state.workspace,
            site_id=site_id,
            category="incident",
            item_id=int(datetime.now().timestamp()),
            config=messaging_cfg,
        )

    with get_db(db_path) as conn:
        cursor = conn.execute(
            "INSERT INTO incidents "
            "(site_id, incident_type, date_time, description, persons_involved, immediate_action, status) "
            "VALUES (?, ?, ?, ?, ?, ?, 'open')",
            (site_id, incident_type, datetime.now().isoformat(), description, sender, "", ),
        )
        incident_id = cursor.lastrowid

    emit_event(
        app_state.db_paths["mona_events"],
        event_type="alert",
        tool_name="safety-form",
        summary=f"Incident #{incident_id} reported via WhatsApp: {incident_type}",
        requires_human_action=True,
    )

    escalated = await _escalate_to_pm(app_state, pm_phone, incident_id, incident_type, description, sender)

    logger.info(
        "Incident #%d created (type=%s, site=%d, escalated=%s)",
        incident_id, incident_type, site_id, escalated,
    )

    return {
        "incident_id": incident_id,
        "incident_type": incident_type,
        "site_id": site_id,
        "escalated": escalated,
        "photo_path": photo_path,
    }


def _parse_incident_text(body: str) -> tuple[str, str]:
    """Extract incident type and description from message text."""
    lower = body.lower()

    type_keywords = {
        "accident": "accident",
        "injury": "accident",
        "hurt": "accident",
        "fall": "accident",
        "collapse": "accident",
        "near miss": "near_miss",
        "near-miss": "near_miss",
        "almost": "near_miss",
        "close call": "near_miss",
        "fire": "dangerous_occurrence",
        "explosion": "dangerous_occurrence",
        "gas leak": "dangerous_occurrence",
        "damage": "property_damage",
        "broken": "property_damage",
    }

    incident_type = "near_miss"
    for keyword, itype in type_keywords.items():
        if keyword in lower:
            incident_type = itype
            break

    description = body.strip()
    for prefix in ("incident", "report", "accident", "emergency"):
        if lower.startswith(prefix):
            description = body[len(prefix):].strip().lstrip(":").strip()
            break

    return incident_type, description or "Incident reported via WhatsApp (no details)"


def _lookup_sender_site(db_path: Any, sender: str) -> tuple[int, str]:
    """Find the site and project manager associated with a phone number.

    Falls back to site_id=1 if no match found.
    """
    clean_number = sender.replace("whatsapp:", "").strip()

    try:
        with get_db(db_path) as conn:
            row = conn.execute(
                "SELECT id, safety_officer, contractor FROM sites WHERE safety_officer LIKE ? AND status = 'active'",
                (f"%{clean_number[-8:]}%",),
            ).fetchone()
            if row:
                return row["id"], row.get("contractor", "") or ""

            first_site = conn.execute(
                "SELECT id, contractor FROM sites WHERE status = 'active' LIMIT 1"
            ).fetchone()
            if first_site:
                return first_site["id"], first_site.get("contractor", "") or ""
    except Exception:
        logger.exception("Error looking up sender site for %s", sender)

    return 1, ""


async def _escalate_to_pm(
    app_state: Any,
    pm_phone: str,
    incident_id: int,
    incident_type: str,
    description: str,
    reporter: str,
) -> bool:
    """Send immediate WhatsApp alert to the project manager."""
    from construction.safety_form.bot.whatsapp_handler import send_whatsapp_message, _get_messaging_config

    if not pm_phone:
        logger.warning("No PM phone for escalation of incident #%d", incident_id)
        return False

    messaging_cfg = _get_messaging_config(app_state)

    type_labels = {
        "accident": "🚨 ACCIDENT",
        "near_miss": "⚠️ Near Miss",
        "dangerous_occurrence": "🔴 Dangerous Occurrence",
        "property_damage": "🟡 Property Damage",
    }
    label = type_labels.get(incident_type, "⚠️ Incident")

    message = (
        f"{label} — Incident #{incident_id}\n\n"
        f"Reported by: {reporter}\n"
        f"Description: {description[:500]}\n\n"
        "Please review immediately in the Safety Dashboard."
    )

    return await send_whatsapp_message(pm_phone, message, messaging_cfg)
