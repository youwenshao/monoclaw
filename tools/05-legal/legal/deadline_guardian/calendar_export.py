"""Generate .ics (iCalendar) files for case deadlines.

Uses the ``icalendar`` library to build RFC 5545-compliant calendar
files.  Each deadline becomes a full-day VEVENT with two VALARM
display reminders (7 days and 1 day before).
"""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from uuid import uuid4

from icalendar import Calendar, Event, Alarm

from openclaw_shared.database import get_db


def export_case_calendar(case_id: int, db_path: str | Path) -> bytes:
    """Build an .ics file containing every deadline for *case_id*.

    Raises ``ValueError`` if the case does not exist.
    Returns the raw ``bytes`` of the serialised calendar.
    """
    with get_db(db_path) as conn:
        case_row = conn.execute(
            "SELECT * FROM cases WHERE id = ?", (case_id,)
        ).fetchone()
        if case_row is None:
            raise ValueError(f"Case {case_id} not found")
        case = dict(case_row)

        deadlines = conn.execute(
            "SELECT * FROM deadlines WHERE case_id = ? ORDER BY due_date ASC",
            (case_id,),
        ).fetchall()

    cal = Calendar()
    cal.add("prodid", "-//OpenClaw Legal//DeadlineGuardian//EN")
    cal.add("version", "2.0")
    cal.add("calscale", "GREGORIAN")
    cal.add("x-wr-calname", f"{case['case_number']} — {case['case_name']}")

    for row in deadlines:
        dl = dict(row)
        event = Event()
        event.add(
            "uid",
            f"dg-{dl['id']}-{uuid4().hex[:8]}@openclaw.legal",
        )
        event.add(
            "summary",
            f"[{case['case_number']}] {dl['deadline_type']}: {dl['description']}",
        )

        due = datetime.fromisoformat(dl["due_date"])
        event.add("dtstart", due.date())
        event.add("dtend", due.date())
        event.add("dtstamp", datetime.now())

        description_lines = [
            f"Case: {case['case_name']}",
            f"Court: {case['court']}",
            f"Solicitor: {case['solicitor_responsible']}",
            f"Basis: {dl.get('statutory_basis') or 'N/A'}",
            f"Status: {dl['status']}",
        ]
        if dl.get("notes"):
            description_lines.append(f"Notes: {dl['notes']}")
        event.add("description", "\n".join(description_lines))

        for days_before in (7, 1):
            alarm = Alarm()
            alarm.add("action", "DISPLAY")
            alarm.add("trigger", timedelta(days=-days_before))
            alarm.add(
                "description",
                f"{days_before}d reminder: {dl['deadline_type']} — {case['case_number']}",
            )
            event.add_component(alarm)

        cal.add_component(event)

    return cal.to_ical()
