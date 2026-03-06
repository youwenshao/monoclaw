"""WhatsApp inbox management — retrieve, filter, and tag messages."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from openclaw_shared.database import get_db


def get_inbox(
    db_path: str | Path,
    limit: int = 50,
    status_filter: str | None = None,
) -> list[dict[str, Any]]:
    """Return messages joined with customer info, newest first.

    *status_filter*: ``"pending"`` returns only messages needing follow-up,
    ``"handled"`` returns resolved ones, or ``None`` for all.
    """
    conditions: list[str] = []
    params: list[Any] = []

    if status_filter == "pending":
        conditions.append("m.requires_followup = 1")
    elif status_filter == "handled":
        conditions.append("m.requires_followup = 0")

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    params.append(limit)

    query = f"""
        SELECT m.*, c.name, c.name_tc, c.phone
        FROM whatsapp_messages m
        LEFT JOIN customers c ON c.id = m.customer_id
        {where}
        ORDER BY m.timestamp DESC
        LIMIT ?
    """

    with get_db(db_path) as conn:
        rows = conn.execute(query, params).fetchall()
    return [dict(r) for r in rows]


def tag_message(db_path: str | Path, msg_id: int, tags: list[str]) -> None:
    """Overwrite tags on a message (stored as comma-separated string)."""
    tag_str = ",".join(tags)
    with get_db(db_path) as conn:
        conn.execute(
            "UPDATE whatsapp_messages SET tags = ? WHERE id = ?",
            (tag_str, msg_id),
        )


def get_pending_count(db_path: str | Path) -> int:
    """Count messages that still require follow-up."""
    with get_db(db_path) as conn:
        row = conn.execute(
            "SELECT COUNT(*) FROM whatsapp_messages WHERE requires_followup = 1"
        ).fetchone()
    return row[0] if row else 0


def record_message(
    db_path: str | Path,
    customer_id: int,
    direction: str,
    text: str,
    msg_type: str = "text",
    requires_followup: bool = False,
) -> int:
    """Insert a new message and return its ID."""
    with get_db(db_path) as conn:
        cursor = conn.execute(
            """INSERT INTO whatsapp_messages
               (customer_id, direction, message_text, message_type, requires_followup)
               VALUES (?, ?, ?, ?, ?)""",
            (customer_id, direction, text, msg_type, requires_followup),
        )
        return cursor.lastrowid  # type: ignore[return-value]
