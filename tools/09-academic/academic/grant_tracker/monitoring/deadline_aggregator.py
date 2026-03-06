"""Unified deadline management – merges scraped deadlines with DB records."""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from openclaw_shared.database import get_db

logger = logging.getLogger("openclaw.academic.grant_tracker.monitoring.aggregator")


def _resolve_status(external_deadline: str | None) -> str:
    if not external_deadline:
        return "upcoming"
    try:
        dl = date.fromisoformat(external_deadline)
    except ValueError:
        return "upcoming"
    today = date.today()
    if dl < today:
        return "closed"
    if (dl - today).days <= 90:
        return "open"
    return "upcoming"


def _ensure_scheme(conn: Any, entry: dict) -> int:
    """Return the scheme id, inserting a new row if the scheme_code is unknown."""
    row = conn.execute(
        "SELECT id FROM grant_schemes WHERE scheme_code = ?",
        (entry["scheme_code"],),
    ).fetchone()
    if row:
        return row["id"]

    agency = "RGC"
    code = entry["scheme_code"]
    if code.startswith("ITF"):
        agency = "ITF"
    elif code.startswith("NSFC"):
        agency = "NSFC"

    cur = conn.execute(
        """INSERT INTO grant_schemes (agency, scheme_name, scheme_code, description, url)
           VALUES (?, ?, ?, ?, ?)""",
        (
            agency,
            entry.get("scheme_name", code),
            code,
            entry.get("description", ""),
            entry.get("call_url", ""),
        ),
    )
    return cur.lastrowid  # type: ignore[return-value]


def aggregate_deadlines(
    db_path: str | Path,
    scraped: list[dict] | None = None,
) -> list[dict]:
    """Merge scraped deadlines into the DB and return the full deadline list.

    For each scraped entry the function:
    1. Ensures the grant_scheme exists (upserts by scheme_code).
    2. Creates or updates a deadline row for that scheme + year.
    3. Recomputes status (upcoming / open / closed) based on today's date.

    Returns all deadlines from the DB after merge.
    """
    if scraped is None:
        scraped = []

    with get_db(db_path) as conn:
        for entry in scraped:
            if not entry.get("scheme_code"):
                continue
            scheme_id = _ensure_scheme(conn, entry)
            dl_date = entry.get("deadline_date")
            year = None
            if dl_date:
                try:
                    year = date.fromisoformat(dl_date).year
                except ValueError:
                    pass

            existing = conn.execute(
                "SELECT id FROM deadlines WHERE scheme_id = ? AND year = ?",
                (scheme_id, year),
            ).fetchone()

            status = _resolve_status(dl_date)
            inst_deadline = (
                compute_institutional_deadline(dl_date) if dl_date else None
            )

            if existing:
                conn.execute(
                    """UPDATE deadlines
                       SET external_deadline = ?, institutional_deadline = ?,
                           call_url = ?, status = ?
                       WHERE id = ?""",
                    (dl_date, inst_deadline, entry.get("call_url"), status, existing["id"]),
                )
            else:
                conn.execute(
                    """INSERT INTO deadlines
                       (scheme_id, year, external_deadline, institutional_deadline, call_url, status)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (scheme_id, year, dl_date, inst_deadline, entry.get("call_url"), status),
                )

        _refresh_statuses(conn)

        rows = conn.execute(
            """SELECT d.*, gs.scheme_name, gs.scheme_code, gs.agency
               FROM deadlines d
               JOIN grant_schemes gs ON gs.id = d.scheme_id
               ORDER BY d.external_deadline ASC NULLS LAST"""
        ).fetchall()

    return [dict(r) for r in rows]


def _refresh_statuses(conn: Any) -> None:
    """Recompute status for all non-closed deadlines."""
    today_iso = date.today().isoformat()
    conn.execute(
        "UPDATE deadlines SET status = 'closed' WHERE external_deadline < ? AND status != 'closed'",
        (today_iso,),
    )
    ninety_days = (date.today() + timedelta(days=90)).isoformat()
    conn.execute(
        """UPDATE deadlines SET status = 'open'
           WHERE external_deadline >= ? AND external_deadline <= ?
             AND status NOT IN ('closed')""",
        (today_iso, ninety_days),
    )
    conn.execute(
        """UPDATE deadlines SET status = 'upcoming'
           WHERE external_deadline > ? AND status NOT IN ('closed', 'open')""",
        (ninety_days,),
    )


def compute_institutional_deadline(
    external_deadline: str,
    offset_days: int = -21,
) -> str:
    """Calculate the institutional (internal) deadline.

    Most HK universities require submissions 2–3 weeks before the
    external agency deadline for internal review.

    Args:
        external_deadline: ISO-format date string of the external deadline.
        offset_days: Number of days to subtract (negative = earlier). Default -21.

    Returns:
        ISO-format date string for the institutional deadline.
    """
    dl = date.fromisoformat(external_deadline)
    return (dl + timedelta(days=offset_days)).isoformat()


def get_upcoming_deadlines(
    db_path: str | Path,
    days_ahead: int = 90,
) -> list[dict]:
    """Fetch deadlines within the next *days_ahead* days.

    Returns deadlines sorted by external_deadline ascending.
    """
    today = date.today()
    cutoff = (today + timedelta(days=days_ahead)).isoformat()
    today_iso = today.isoformat()

    with get_db(db_path) as conn:
        rows = conn.execute(
            """SELECT d.*, gs.scheme_name, gs.scheme_code, gs.agency
               FROM deadlines d
               JOIN grant_schemes gs ON gs.id = d.scheme_id
               WHERE d.external_deadline >= ? AND d.external_deadline <= ?
               ORDER BY d.external_deadline ASC""",
            (today_iso, cutoff),
        ).fetchall()

    return [dict(r) for r in rows]


def get_calendar_events(db_path: str | Path) -> list[dict]:
    """Return deadlines formatted for FullCalendar JSON.

    Each event has: id, title, start, end, url, color, extendedProps.
    """
    color_map = {
        "RGC": "#3b82f6",
        "ITF": "#10b981",
        "NSFC": "#ef4444",
        "Other": "#8b5cf6",
    }

    with get_db(db_path) as conn:
        rows = conn.execute(
            """SELECT d.*, gs.scheme_name, gs.scheme_code, gs.agency
               FROM deadlines d
               JOIN grant_schemes gs ON gs.id = d.scheme_id
               WHERE d.external_deadline IS NOT NULL
               ORDER BY d.external_deadline ASC"""
        ).fetchall()

    events: list[dict] = []
    for row in rows:
        r = dict(row)
        agency = r.get("agency", "Other")
        events.append({
            "id": f"deadline-{r['id']}",
            "title": f"{r['scheme_code']} – {r['scheme_name']}",
            "start": r["external_deadline"],
            "end": r["external_deadline"],
            "url": r.get("call_url", ""),
            "color": color_map.get(agency, color_map["Other"]),
            "extendedProps": {
                "deadline_id": r["id"],
                "scheme_id": r["scheme_id"],
                "agency": agency,
                "status": r.get("status", "upcoming"),
                "institutional_deadline": r.get("institutional_deadline"),
                "notes": r.get("notes", ""),
            },
        })

        if r.get("institutional_deadline"):
            events.append({
                "id": f"inst-deadline-{r['id']}",
                "title": f"[Internal] {r['scheme_code']}",
                "start": r["institutional_deadline"],
                "end": r["institutional_deadline"],
                "color": "#f59e0b",
                "extendedProps": {
                    "deadline_id": r["id"],
                    "type": "institutional",
                    "agency": agency,
                },
            })

    return events
