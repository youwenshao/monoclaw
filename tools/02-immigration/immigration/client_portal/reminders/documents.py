"""Document deadline tracking for the ClientPortal Bot."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from openclaw_shared.database import get_db


def get_overdue_documents(db_path: Any) -> list[dict]:
    """Return all outstanding documents that are past their deadline."""
    today = date.today().isoformat()
    with get_db(db_path) as conn:
        rows = conn.execute(
            """SELECT od.*, c.reference_code, c.client_name, c.client_phone,
                      c.language_pref, c.scheme
               FROM outstanding_documents od
               JOIN cases c ON c.id = od.case_id
               WHERE od.received = 0 AND od.deadline < ?
               ORDER BY od.deadline ASC""",
            (today,),
        ).fetchall()
    return [dict(r) for r in rows]


def get_upcoming_deadlines(db_path: Any, days_ahead: int = 14) -> list[dict]:
    """Return outstanding documents with deadlines within the next N days."""
    today = date.today()
    cutoff = (today + timedelta(days=days_ahead)).isoformat()
    with get_db(db_path) as conn:
        rows = conn.execute(
            """SELECT od.*, c.reference_code, c.client_name, c.client_phone,
                      c.language_pref, c.scheme
               FROM outstanding_documents od
               JOIN cases c ON c.id = od.case_id
               WHERE od.received = 0
                 AND od.deadline >= ?
                 AND od.deadline <= ?
               ORDER BY od.deadline ASC""",
            (today.isoformat(), cutoff),
        ).fetchall()
    return [dict(r) for r in rows]
