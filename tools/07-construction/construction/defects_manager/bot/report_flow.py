"""Guided WhatsApp conversation flow for defect reporting.

Flow: photo -> location (floor/unit) -> description -> category confirmation -> create defect.
"""

from __future__ import annotations

import logging
from typing import Any

from openclaw_shared.database import get_db

logger = logging.getLogger("openclaw.construction.defects_manager.bot.report_flow")

_sessions: dict[str, dict[str, Any]] = {}

STEPS = ("photo", "location", "description", "confirm")


def _get_session(sender: str) -> dict[str, Any]:
    if sender not in _sessions:
        _sessions[sender] = {"step": "photo", "data": {}}
    return _sessions[sender]


def _clear_session(sender: str) -> None:
    _sessions.pop(sender, None)


async def process_report_step(
    app_state: Any,
    sender: str,
    message: str,
    media_url: str | None = None,
) -> dict:
    """Advance the guided reporting flow by one step.

    Returns ``{"message": str, "complete": bool, "defect_id": int | None}``.
    """
    lower = message.lower().strip()

    if lower in ("cancel", "restart", "取消"):
        _clear_session(sender)
        return {"message": "Report cancelled. Send a photo to start a new report.", "complete": False, "defect_id": None}

    session = _get_session(sender)
    step = session["step"]
    data = session["data"]

    # Step 1: photo
    if step == "photo":
        if not media_url and not data.get("photo_path"):
            return {
                "message": "📸 Please send a photo of the defect to begin your report.",
                "complete": False,
                "defect_id": None,
            }
        if media_url:
            data["photo_path"] = media_url
        if message and not media_url:
            data["initial_text"] = message
        session["step"] = "location"
        return {
            "message": "Photo received. Please provide the location:\nFormat: Floor/Unit (e.g. 12/A)",
            "complete": False,
            "defect_id": None,
        }

    # Step 2: location
    if step == "location":
        parts = message.replace("/", " ").split()
        data["floor"] = parts[0] if parts else ""
        data["unit"] = parts[1] if len(parts) > 1 else ""
        data["location_detail"] = message
        session["step"] = "description"
        return {
            "message": "Location noted. Please describe the defect (e.g. water dripping from ceiling).",
            "complete": False,
            "defect_id": None,
        }

    # Step 3: description
    if step == "description":
        data["description"] = message

        from construction.defects_manager.defects.categorizer import categorize_defect

        llm = getattr(app_state, "llm", None)
        category = await categorize_defect(llm, message, data.get("photo_path"))
        data["category"] = category

        session["step"] = "confirm"
        return {
            "message": (
                f"Category: {category.replace('_', ' ').title()}\n"
                f"Location: {data.get('floor', '?')}F / Unit {data.get('unit', '?')}\n"
                f"Description: {message}\n\n"
                "Reply YES to submit or CANCEL to start over."
            ),
            "complete": False,
            "defect_id": None,
        }

    # Step 4: confirm
    if step == "confirm":
        if lower not in ("yes", "y", "ok", "confirm", "確認"):
            _clear_session(sender)
            return {"message": "Report cancelled.", "complete": False, "defect_id": None}

        defect_id = _create_defect(app_state, sender, data)
        _clear_session(sender)
        return {
            "message": f"Defect #{defect_id} created. We will notify you of status updates.",
            "complete": True,
            "defect_id": defect_id,
        }

    _clear_session(sender)
    return {"message": "Send a photo to report a defect.", "complete": False, "defect_id": None}


def _create_defect(app_state: Any, sender: str, data: dict) -> int:
    """Insert a defect record from the collected flow data."""
    db_paths = getattr(app_state, "db_paths", {})
    db = db_paths.get("defects_manager")
    if not db:
        logger.error("No defects_manager db_path configured")
        return -1

    with get_db(db) as conn:
        property_row = conn.execute("SELECT id FROM properties LIMIT 1").fetchone()
        property_id = property_row["id"] if property_row else 1

        cursor = conn.execute(
            "INSERT INTO defects (property_id, unit, floor, location_detail, category, "
            "description, reported_by, reported_phone, photo_path, priority) "
            "VALUES (?,?,?,?,?,?,?,?,?,?)",
            (
                property_id,
                data.get("unit", ""),
                data.get("floor", ""),
                data.get("location_detail", ""),
                data.get("category", "other"),
                data.get("description", ""),
                sender,
                sender,
                data.get("photo_path", ""),
                "normal",
            ),
        )
        defect_id: int = cursor.lastrowid  # type: ignore[assignment]

    from construction.defects_manager.defects.priority_engine import auto_escalate
    auto_escalate(db, defect_id, data.get("category", "other"))

    logger.info("Defect #%d created via WhatsApp from %s", defect_id, sender)
    return defect_id
