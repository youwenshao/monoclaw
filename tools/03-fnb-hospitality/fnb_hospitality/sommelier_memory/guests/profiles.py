"""Guest profile CRUD with photo support, phone-based identity, and PDPO-compliant deletion."""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Any

from openclaw_shared.database import get_db
from openclaw_shared.mona_events import emit_event

HK_PHONE_RE = re.compile(r"^\+852[5679]\d{7}$")


def _row_to_dict(row: Any) -> dict[str, Any]:
    return dict(row) if row else {}


def _validate_phone(phone: str) -> str:
    phone = phone.strip()
    if not HK_PHONE_RE.match(phone):
        raise ValueError(f"Invalid HK phone number: {phone}")
    return phone


def create_guest(
    db_path: str | Path,
    name: str,
    phone: str,
    *,
    preferred_name: str = "",
    email: str = "",
    photo_path: str = "",
    language_pref: str = "cantonese",
    tags: str = "",
    notes: str = "",
    mona_db: str | Path | None = None,
) -> dict[str, Any]:
    phone = _validate_phone(phone)
    now = datetime.now().isoformat()

    with get_db(db_path) as conn:
        existing = conn.execute(
            "SELECT id FROM sm_guests WHERE phone = ?", (phone,)
        ).fetchone()
        if existing:
            raise ValueError(f"Guest with phone {phone} already exists (id={existing[0]})")

        cursor = conn.execute(
            """INSERT INTO sm_guests
               (name, preferred_name, phone, email, photo_path, language_pref,
                tags, notes, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (name, preferred_name, phone, email, photo_path, language_pref,
             tags, notes, now, now),
        )
        guest_id = cursor.lastrowid
        row = conn.execute("SELECT * FROM sm_guests WHERE id = ?", (guest_id,)).fetchone()

    if mona_db:
        emit_event(
            mona_db,
            event_type="action_completed",
            tool_name="sommelier-memory",
            summary=f"New guest created: {name} ({phone})",
        )

    return _row_to_dict(row)


def get_guest(db_path: str | Path, guest_id: int) -> dict[str, Any]:
    with get_db(db_path) as conn:
        row = conn.execute("SELECT * FROM sm_guests WHERE id = ?", (guest_id,)).fetchone()
        if not row:
            return {}
        guest = _row_to_dict(row)

        guest["dietary_info"] = [
            dict(r) for r in conn.execute(
                "SELECT * FROM dietary_info WHERE guest_id = ?", (guest_id,)
            ).fetchall()
        ]
        guest["celebrations"] = [
            dict(r) for r in conn.execute(
                "SELECT * FROM celebrations WHERE guest_id = ?", (guest_id,)
            ).fetchall()
        ]
        guest["preferences"] = [
            dict(r) for r in conn.execute(
                "SELECT * FROM preferences WHERE guest_id = ?", (guest_id,)
            ).fetchall()
        ]

    return guest


def get_guest_by_phone(db_path: str | Path, phone: str) -> dict[str, Any]:
    phone = _validate_phone(phone)
    with get_db(db_path) as conn:
        row = conn.execute("SELECT * FROM sm_guests WHERE phone = ?", (phone,)).fetchone()
        if not row:
            return {}
        guest = _row_to_dict(row)
        guest_id = guest["id"]

        guest["dietary_info"] = [
            dict(r) for r in conn.execute(
                "SELECT * FROM dietary_info WHERE guest_id = ?", (guest_id,)
            ).fetchall()
        ]
        guest["celebrations"] = [
            dict(r) for r in conn.execute(
                "SELECT * FROM celebrations WHERE guest_id = ?", (guest_id,)
            ).fetchall()
        ]
        guest["preferences"] = [
            dict(r) for r in conn.execute(
                "SELECT * FROM preferences WHERE guest_id = ?", (guest_id,)
            ).fetchall()
        ]

    return guest


def update_guest(
    db_path: str | Path,
    guest_id: int,
    *,
    mona_db: str | Path | None = None,
    **fields: Any,
) -> dict[str, Any]:
    allowed = {
        "name", "preferred_name", "phone", "email", "photo_path",
        "language_pref", "vip_tier", "tags", "notes",
    }
    updates = {k: v for k, v in fields.items() if k in allowed and v is not None}
    if not updates:
        return get_guest(db_path, guest_id)

    if "phone" in updates:
        updates["phone"] = _validate_phone(updates["phone"])

    updates["updated_at"] = datetime.now().isoformat()
    set_clause = ", ".join(f"{k} = ?" for k in updates)
    values = list(updates.values()) + [guest_id]

    with get_db(db_path) as conn:
        conn.execute(f"UPDATE sm_guests SET {set_clause} WHERE id = ?", values)  # noqa: S608
        row = conn.execute("SELECT * FROM sm_guests WHERE id = ?", (guest_id,)).fetchone()

    if mona_db:
        changed = ", ".join(updates.keys() - {"updated_at"})
        emit_event(
            mona_db,
            event_type="info",
            tool_name="sommelier-memory",
            summary=f"Guest #{guest_id} updated: {changed}",
        )

    return get_guest(db_path, guest_id)


def delete_guest(
    db_path: str | Path,
    guest_id: int,
    *,
    mona_db: str | Path | None = None,
) -> bool:
    """PDPO-compliant full deletion — removes guest and all associated data."""
    with get_db(db_path) as conn:
        row = conn.execute("SELECT name, phone FROM sm_guests WHERE id = ?", (guest_id,)).fetchone()
        if not row:
            return False

        guest_name = row[0]
        conn.execute("DELETE FROM dietary_info WHERE guest_id = ?", (guest_id,))
        conn.execute("DELETE FROM celebrations WHERE guest_id = ?", (guest_id,))
        conn.execute("DELETE FROM visits WHERE guest_id = ?", (guest_id,))
        conn.execute("DELETE FROM preferences WHERE guest_id = ?", (guest_id,))
        conn.execute("DELETE FROM sm_guests WHERE id = ?", (guest_id,))

    if mona_db:
        emit_event(
            mona_db,
            event_type="action_completed",
            tool_name="sommelier-memory",
            summary=f"PDPO deletion completed for guest #{guest_id} ({guest_name})",
            details="All personal data removed from sm_guests, dietary_info, celebrations, visits, preferences",
            requires_human_action=False,
        )

    return True


def search_guests(
    db_path: str | Path,
    query: str,
    *,
    tags: str | None = None,
    vip_tier: str | None = None,
) -> list[dict[str, Any]]:
    conditions: list[str] = []
    params: list[Any] = []

    if query:
        conditions.append(
            "(name LIKE ? OR preferred_name LIKE ? OR phone LIKE ? OR email LIKE ?)"
        )
        like = f"%{query}%"
        params.extend([like, like, like, like])

    if tags:
        for tag in tags.split(","):
            tag = tag.strip()
            if tag:
                conditions.append("tags LIKE ?")
                params.append(f"%{tag}%")

    if vip_tier:
        conditions.append("vip_tier = ?")
        params.append(vip_tier)

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    with get_db(db_path) as conn:
        rows = conn.execute(
            f"SELECT * FROM sm_guests {where} ORDER BY last_visit DESC NULLS LAST, name",  # noqa: S608
            params,
        ).fetchall()

    return [_row_to_dict(r) for r in rows]


def list_guests(
    db_path: str | Path,
    limit: int = 50,
    offset: int = 0,
) -> list[dict[str, Any]]:
    with get_db(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM sm_guests ORDER BY last_visit DESC NULLS LAST, name LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()
    return [_row_to_dict(r) for r in rows]
