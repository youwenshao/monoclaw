"""Dietary/allergy CRUD with severity levels, audit logging, and HK-common defaults."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from openclaw_shared.database import get_db
from openclaw_shared.mona_events import emit_event

logger = logging.getLogger("openclaw.fnb-hospitality.sommelier-memory.preferences")

SEVERITY_LEVELS = ("mild", "moderate", "severe", "anaphylactic")
DIETARY_TYPES = ("allergy", "intolerance", "preference", "restriction")
PREFERENCE_STRENGTHS = ("dislike", "neutral", "like", "love")

HK_COMMON_ALLERGENS = [
    {"type": "allergy", "item": "MSG", "severity": "moderate"},
    {"type": "allergy", "item": "shellfish", "severity": "severe"},
    {"type": "allergy", "item": "peanut", "severity": "severe"},
    {"type": "intolerance", "item": "lactose", "severity": "moderate"},
]


def _row_to_dict(row: Any) -> dict[str, Any]:
    return dict(row) if row else {}


def _audit_log(
    db_path: str | Path,
    info_id: int,
    guest_id: int,
    action: str,
    old_values: dict[str, Any] | None,
    new_values: dict[str, Any] | None,
) -> None:
    """Log allergy modifications for safety audit trail.

    Stored as a mona event with structured details so the audit history
    is queryable from the activity feed.
    """
    details = json.dumps({
        "info_id": info_id,
        "guest_id": guest_id,
        "action": action,
        "old": old_values,
        "new": new_values,
        "timestamp": datetime.now().isoformat(),
    })
    logger.info("Dietary audit: %s info_id=%d guest_id=%d", action, info_id, guest_id)
    emit_event(
        db_path,
        event_type="info",
        tool_name="sommelier-memory",
        summary=f"Dietary info {action} for guest #{guest_id} (info #{info_id})",
        details=details,
    )


def add_dietary_info(
    db_path: str | Path,
    guest_id: int,
    type_: str,
    item: str,
    severity: str | None = None,
    notes: str = "",
    *,
    mona_db: str | Path | None = None,
) -> dict[str, Any]:
    if type_ not in DIETARY_TYPES:
        raise ValueError(f"type must be one of {DIETARY_TYPES}")
    if severity and severity not in SEVERITY_LEVELS:
        raise ValueError(f"severity must be one of {SEVERITY_LEVELS}")

    with get_db(db_path) as conn:
        guest = conn.execute("SELECT id FROM sm_guests WHERE id = ?", (guest_id,)).fetchone()
        if not guest:
            raise ValueError(f"Guest {guest_id} not found")

        cursor = conn.execute(
            "INSERT INTO dietary_info (guest_id, type, item, severity, notes) VALUES (?,?,?,?,?)",
            (guest_id, type_, item, severity, notes),
        )
        info_id = cursor.lastrowid
        row = conn.execute("SELECT * FROM dietary_info WHERE id = ?", (info_id,)).fetchone()

    if mona_db:
        _audit_log(mona_db, info_id, guest_id, "added", None, {"type": type_, "item": item, "severity": severity})

    return _row_to_dict(row)


def update_dietary_info(
    db_path: str | Path,
    info_id: int,
    *,
    mona_db: str | Path | None = None,
    **fields: Any,
) -> dict[str, Any]:
    allowed = {"type", "item", "severity", "notes"}
    updates = {k: v for k, v in fields.items() if k in allowed and v is not None}
    if not updates:
        with get_db(db_path) as conn:
            row = conn.execute("SELECT * FROM dietary_info WHERE id = ?", (info_id,)).fetchone()
        return _row_to_dict(row)

    if "type" in updates and updates["type"] not in DIETARY_TYPES:
        raise ValueError(f"type must be one of {DIETARY_TYPES}")
    if "severity" in updates and updates["severity"] not in SEVERITY_LEVELS:
        raise ValueError(f"severity must be one of {SEVERITY_LEVELS}")

    with get_db(db_path) as conn:
        old_row = conn.execute("SELECT * FROM dietary_info WHERE id = ?", (info_id,)).fetchone()
        if not old_row:
            raise ValueError(f"Dietary info {info_id} not found")
        old_data = dict(old_row)

        set_clause = ", ".join(f"{k} = ?" for k in updates)
        values = list(updates.values()) + [info_id]
        conn.execute(f"UPDATE dietary_info SET {set_clause} WHERE id = ?", values)  # noqa: S608

        row = conn.execute("SELECT * FROM dietary_info WHERE id = ?", (info_id,)).fetchone()

    if mona_db:
        _audit_log(mona_db, info_id, old_data["guest_id"], "updated", old_data, updates)

    return _row_to_dict(row)


def remove_dietary_info(
    db_path: str | Path,
    info_id: int,
    *,
    mona_db: str | Path | None = None,
) -> bool:
    """Remove dietary info. Severe/anaphylactic allergies are soft-deleted (notes appended)
    rather than actually deleted, for patient safety."""
    with get_db(db_path) as conn:
        row = conn.execute("SELECT * FROM dietary_info WHERE id = ?", (info_id,)).fetchone()
        if not row:
            return False

        info = dict(row)

        if info["severity"] in ("severe", "anaphylactic"):
            ts = datetime.now().isoformat()
            existing_notes = info.get("notes") or ""
            new_notes = f"{existing_notes}\n[DEACTIVATED {ts}] — marked for removal but retained for safety".strip()
            conn.execute(
                "UPDATE dietary_info SET notes = ? WHERE id = ?",
                (new_notes, info_id),
            )
            if mona_db:
                _audit_log(
                    mona_db, info_id, info["guest_id"], "soft_deleted",
                    info, {"notes": new_notes},
                )
                emit_event(
                    mona_db,
                    event_type="alert",
                    tool_name="sommelier-memory",
                    summary=f"Severe allergy record #{info_id} retained for safety (soft-delete only)",
                    requires_human_action=True,
                )
            return True

        conn.execute("DELETE FROM dietary_info WHERE id = ?", (info_id,))

    if mona_db:
        _audit_log(mona_db, info_id, info["guest_id"], "deleted", info, None)

    return True


def get_dietary_info(db_path: str | Path, guest_id: int) -> list[dict[str, Any]]:
    with get_db(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM dietary_info WHERE guest_id = ? ORDER BY severity DESC, item",
            (guest_id,),
        ).fetchall()
    return [_row_to_dict(r) for r in rows]


def add_preference(
    db_path: str | Path,
    guest_id: int,
    category: str,
    preference: str,
    strength: str = "like",
    notes: str = "",
    *,
    mona_db: str | Path | None = None,
) -> dict[str, Any]:
    if strength not in PREFERENCE_STRENGTHS:
        raise ValueError(f"strength must be one of {PREFERENCE_STRENGTHS}")

    with get_db(db_path) as conn:
        guest = conn.execute("SELECT id FROM sm_guests WHERE id = ?", (guest_id,)).fetchone()
        if not guest:
            raise ValueError(f"Guest {guest_id} not found")

        cursor = conn.execute(
            "INSERT INTO preferences (guest_id, category, preference, strength, notes) VALUES (?,?,?,?,?)",
            (guest_id, category, preference, strength, notes),
        )
        pref_id = cursor.lastrowid
        row = conn.execute("SELECT * FROM preferences WHERE id = ?", (pref_id,)).fetchone()

    if mona_db:
        emit_event(
            mona_db,
            event_type="info",
            tool_name="sommelier-memory",
            summary=f"Preference added for guest #{guest_id}: {category} — {preference} ({strength})",
        )

    return _row_to_dict(row)


def get_preferences(db_path: str | Path, guest_id: int) -> list[dict[str, Any]]:
    with get_db(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM preferences WHERE guest_id = ? ORDER BY category, preference",
            (guest_id,),
        ).fetchall()
    return [_row_to_dict(r) for r in rows]


def get_hk_common_allergens() -> list[dict[str, str | None]]:
    """Return the default HK-common allergens list for quick-add UI."""
    return list(HK_COMMON_ALLERGENS)
