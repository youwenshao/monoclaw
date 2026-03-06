"""Parse incoming WhatsApp messages to update assignment completion status."""

from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import Any

from openclaw_shared.database import get_db
from openclaw_shared.mona_events import emit_event

logger = logging.getLogger("openclaw.construction.site_coordinator.progress_collector")

_COMPLETION_PATTERNS = [
    re.compile(r"✅"),
    re.compile(r"\b(?:done|completed|finished|complete)\b", re.IGNORECASE),
]

_CANCELLATION_PATTERNS = [
    re.compile(r"❌"),
    re.compile(r"\b(?:cannot|can't|unable|cancel)\b", re.IGNORECASE),
]


async def handle_incoming(form_data: dict[str, Any], app_state: Any) -> None:
    """Process an incoming WhatsApp webhook payload.

    Matches the sender's phone to a contractor, finds their most recent
    dispatched assignment, and updates its status based on message content.
    """
    from_number = str(form_data.get("From", "")).replace("whatsapp:", "")
    body = str(form_data.get("Body", "")).strip()
    media_url = form_data.get("MediaUrl0")

    if not from_number or not body:
        logger.debug("Ignoring empty webhook payload")
        return

    db_path = _get_db_path(app_state)
    if not db_path:
        logger.error("No site_coordinator db_path in app_state")
        return

    contractor = _find_contractor_by_phone(db_path, from_number)
    if not contractor:
        logger.info("No contractor found for phone %s", from_number)
        return

    assignment = _find_latest_dispatched(db_path, contractor["id"])
    if not assignment:
        logger.info("No dispatched assignment for contractor %d", contractor["id"])
        return

    if _matches_completion(body):
        _update_status(db_path, assignment["id"], "completed", body)
        logger.info(
            "Assignment #%d marked completed by %s",
            assignment["id"], contractor.get("company_name", from_number),
        )
        _emit_completion_event(app_state, assignment, contractor, "completed")

    elif _matches_cancellation(body):
        _update_status(db_path, assignment["id"], "cancelled", body)
        logger.info(
            "Assignment #%d cancelled by %s",
            assignment["id"], contractor.get("company_name", from_number),
        )
        _emit_completion_event(app_state, assignment, contractor, "cancelled")

    else:
        logger.debug(
            "Unrecognised message from %s: %s", from_number, body[:100],
        )


def _get_db_path(app_state: Any) -> str | None:
    db_paths = getattr(app_state, "db_paths", {})
    path = db_paths.get("site_coordinator")
    return str(path) if path else None


def _find_contractor_by_phone(db_path: str, phone: str) -> dict | None:
    normalized = phone.lstrip("+").replace(" ", "").replace("-", "")
    with get_db(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM contractors WHERE REPLACE(REPLACE(whatsapp_number, ' ', ''), '-', '') "
            "LIKE '%' || ? OR whatsapp_number = ?",
            (normalized[-8:], phone),
        ).fetchone()
    return dict(row) if row else None


def _find_latest_dispatched(db_path: str, contractor_id: int) -> dict | None:
    with get_db(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM schedule_assignments "
            "WHERE contractor_id = ? AND status = 'dispatched' "
            "ORDER BY assignment_date DESC, start_time DESC LIMIT 1",
            (contractor_id,),
        ).fetchone()
    return dict(row) if row else None


def _matches_completion(body: str) -> bool:
    return any(p.search(body) for p in _COMPLETION_PATTERNS)


def _matches_cancellation(body: str) -> bool:
    return any(p.search(body) for p in _CANCELLATION_PATTERNS)


def _update_status(db_path: str, assignment_id: int, status: str, notes: str) -> None:
    with get_db(db_path) as conn:
        if status == "completed":
            conn.execute(
                "UPDATE schedule_assignments SET status = ?, completed_at = ?, completion_notes = ? "
                "WHERE id = ?",
                (status, datetime.now().isoformat(), notes[:500], assignment_id),
            )
        else:
            conn.execute(
                "UPDATE schedule_assignments SET status = ?, completion_notes = ? WHERE id = ?",
                (status, notes[:500], assignment_id),
            )


def _emit_completion_event(
    app_state: Any, assignment: dict, contractor: dict, status: str
) -> None:
    db_paths = getattr(app_state, "db_paths", {})
    mona_db = db_paths.get("mona_events")
    if not mona_db:
        return

    company = contractor.get("company_name", f"Contractor {contractor['id']}")
    summary = (
        f"Assignment #{assignment['id']} {status} by {company} "
        f"(site {assignment.get('site_id', '?')}, {assignment.get('trade', 'general')})"
    )
    emit_event(
        mona_db,
        event_type="action_completed" if status == "completed" else "alert",
        tool_name="site-coordinator",
        summary=summary,
        requires_human_action=(status == "cancelled"),
    )
