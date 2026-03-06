"""Mona activity protocol — event writer and reader for the GUI activity feed."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from openclaw_shared.database import get_db, run_migrations


MONA_EVENTS_SCHEMA = """
CREATE TABLE IF NOT EXISTS mona_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type TEXT CHECK(event_type IN (
        'action_started','action_completed','approval_needed','error','alert','info'
    )) NOT NULL,
    tool_name TEXT NOT NULL,
    summary TEXT NOT NULL,
    details TEXT,
    requires_human_action BOOLEAN DEFAULT FALSE,
    acknowledged BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""


def init_mona_db(db_path: str | Path) -> None:
    run_migrations(db_path, MONA_EVENTS_SCHEMA)


def emit_event(
    db_path: str | Path,
    *,
    event_type: str,
    tool_name: str,
    summary: str,
    details: str = "",
    requires_human_action: bool = False,
) -> int:
    """Write an event and return its ID."""
    with get_db(db_path) as conn:
        cursor = conn.execute(
            """INSERT INTO mona_events
               (event_type, tool_name, summary, details, requires_human_action)
               VALUES (?, ?, ?, ?, ?)""",
            (event_type, tool_name, summary, details, requires_human_action),
        )
        return cursor.lastrowid  # type: ignore[return-value]


def get_events(
    db_path: str | Path,
    *,
    since: datetime | None = None,
    limit: int = 50,
    unacknowledged_only: bool = False,
) -> list[dict[str, Any]]:
    """Read events, newest first."""
    conditions = []
    params: list[Any] = []
    if since:
        conditions.append("created_at > ?")
        params.append(since.isoformat())
    if unacknowledged_only:
        conditions.append("acknowledged = 0")

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    params.append(limit)

    with get_db(db_path) as conn:
        rows = conn.execute(
            f"SELECT * FROM mona_events {where} ORDER BY created_at DESC LIMIT ?",  # noqa: S608
            params,
        ).fetchall()
        return [dict(r) for r in rows]


def acknowledge_event(db_path: str | Path, event_id: int) -> None:
    with get_db(db_path) as conn:
        conn.execute(
            "UPDATE mona_events SET acknowledged = 1 WHERE id = ?", (event_id,)
        )
