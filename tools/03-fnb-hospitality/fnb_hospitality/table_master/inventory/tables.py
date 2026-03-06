"""Table status management — CRUD and state-machine transitions.

Valid status transitions::

    available → reserved → occupied → clearing → available

Any status can also transition to ``maintenance`` and back to ``available``.
"""

from __future__ import annotations

import logging
from typing import Any

from openclaw_shared.database import get_db

logger = logging.getLogger("openclaw.table_master.inventory.tables")

VALID_STATUSES = {"available", "reserved", "occupied", "clearing", "maintenance"}

VALID_TRANSITIONS: dict[str, set[str]] = {
    "available": {"reserved", "occupied", "maintenance"},
    "reserved": {"occupied", "available", "maintenance"},
    "occupied": {"clearing", "maintenance"},
    "clearing": {"available", "maintenance"},
    "maintenance": {"available"},
}


def get_all_tables(db_path: str) -> list[dict[str, Any]]:
    """Return every table with its current status and assigned booking info."""
    with get_db(db_path) as conn:
        rows = conn.execute(
            """SELECT t.*,
                      b.guest_name AS current_guest,
                      b.party_size AS current_party_size,
                      b.booking_time AS current_booking_time,
                      b.status AS booking_status
               FROM tables t
               LEFT JOIN bookings b ON b.id = t.current_booking_id
               ORDER BY t.table_number"""
        ).fetchall()
    return [dict(r) for r in rows]


def get_table(db_path: str, table_id: int) -> dict[str, Any] | None:
    """Return a single table's details, or ``None`` if not found."""
    with get_db(db_path) as conn:
        row = conn.execute(
            """SELECT t.*,
                      b.guest_name AS current_guest,
                      b.party_size AS current_party_size,
                      b.booking_time AS current_booking_time,
                      b.end_time AS current_end_time,
                      b.status AS booking_status
               FROM tables t
               LEFT JOIN bookings b ON b.id = t.current_booking_id
               WHERE t.id = ?""",
            (table_id,),
        ).fetchone()
    return dict(row) if row else None


def update_table_status(
    db_path: str,
    table_id: int,
    new_status: str,
) -> dict[str, Any]:
    """Transition a table to a new status, enforcing the state machine.

    When transitioning to ``available``, the ``current_booking_id`` is cleared.

    Returns a dict with the result or an error message.
    """
    new_status = new_status.lower().strip()
    if new_status not in VALID_STATUSES:
        return {"error": f"Invalid status '{new_status}'. Must be one of: {', '.join(sorted(VALID_STATUSES))}"}

    with get_db(db_path) as conn:
        row = conn.execute("SELECT * FROM tables WHERE id = ?", (table_id,)).fetchone()
        if not row:
            return {"error": f"Table {table_id} not found"}

        current = dict(row)
        old_status = current["status"]

        allowed = VALID_TRANSITIONS.get(old_status, set())
        if new_status not in allowed:
            return {
                "error": f"Cannot transition from '{old_status}' to '{new_status}'",
                "allowed": sorted(allowed),
            }

        updates = {"status": new_status}
        if new_status == "available":
            updates["current_booking_id"] = None

        set_clause = ", ".join(f"{k} = ?" for k in updates)
        values = list(updates.values()) + [table_id]
        conn.execute(f"UPDATE tables SET {set_clause} WHERE id = ?", values)

    return {
        "table_id": table_id,
        "table_number": current["table_number"],
        "old_status": old_status,
        "new_status": new_status,
    }


def create_table(
    db_path: str,
    *,
    table_number: str,
    seats: int,
    section: str = "main",
    is_combinable: bool = False,
    combine_with: str | None = None,
    location_type: str = "standard",
) -> dict[str, Any]:
    """Insert a new table into the inventory."""
    with get_db(db_path) as conn:
        existing = conn.execute(
            "SELECT id FROM tables WHERE table_number = ?", (table_number,)
        ).fetchone()
        if existing:
            return {"error": f"Table {table_number} already exists"}

        cursor = conn.execute(
            """INSERT INTO tables
               (table_number, seats, section, is_combinable, combine_with, location_type, status)
               VALUES (?,?,?,?,?,?,?)""",
            (table_number, seats, section, is_combinable, combine_with, location_type, "available"),
        )
        table_id = cursor.lastrowid

    return {
        "id": table_id,
        "table_number": table_number,
        "seats": seats,
        "section": section,
        "status": "available",
    }


def delete_table(db_path: str, table_id: int) -> dict[str, Any]:
    """Remove a table from the inventory (only if available and unbooked)."""
    with get_db(db_path) as conn:
        row = conn.execute("SELECT * FROM tables WHERE id = ?", (table_id,)).fetchone()
        if not row:
            return {"error": f"Table {table_id} not found"}

        table = dict(row)
        if table["status"] != "available":
            return {"error": f"Cannot delete table in '{table['status']}' status"}
        if table.get("current_booking_id"):
            return {"error": "Cannot delete table with an active booking"}

        conn.execute("DELETE FROM tables WHERE id = ?", (table_id,))

    return {"deleted": True, "table_id": table_id, "table_number": table["table_number"]}


def get_tables_by_status(db_path: str, status: str) -> list[dict[str, Any]]:
    """Return tables filtered by status."""
    with get_db(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM tables WHERE status = ? ORDER BY table_number",
            (status,),
        ).fetchall()
    return [dict(r) for r in rows]


def get_table_summary(db_path: str) -> dict[str, int]:
    """Return counts of tables grouped by status."""
    with get_db(db_path) as conn:
        rows = conn.execute(
            "SELECT status, COUNT(*) as cnt FROM tables GROUP BY status"
        ).fetchall()
    return {r["status"]: r["cnt"] for r in rows}
