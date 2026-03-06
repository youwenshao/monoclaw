"""Consultation scheduling for the ClientPortal Bot."""

from __future__ import annotations

from datetime import date, datetime, time as dt_time, timedelta
from textwrap import dedent


def get_available_slots(
    target_date: date,
    business_hours: str,
    saturday_hours: str,
    holidays: list[str],
) -> list[dict]:
    """Generate 1-hour consultation slots for the given date.

    Args:
        target_date: The date to generate slots for.
        business_hours: "HH:MM-HH:MM" for Mon-Fri, e.g. "09:00-18:00".
        saturday_hours: "HH:MM-HH:MM" for Saturday, e.g. "09:00-13:00".
        holidays: List of ISO date strings for public holidays.

    Returns:
        List of dicts with start, end, available keys.
    """
    holiday_set = {date.fromisoformat(h) for h in holidays}

    if target_date in holiday_set:
        return []

    weekday = target_date.weekday()

    if weekday == 6:
        return []

    if weekday == 5:
        hours_str = saturday_hours
    else:
        hours_str = business_hours

    open_time, close_time = _parse_hours(hours_str)
    slots: list[dict] = []

    current = datetime.combine(target_date, open_time)
    end_of_day = datetime.combine(target_date, close_time)

    while current + timedelta(hours=1) <= end_of_day:
        slot_end = current + timedelta(hours=1)
        slots.append({
            "start": current.strftime("%H:%M"),
            "end": slot_end.strftime("%H:%M"),
            "start_iso": current.isoformat(),
            "end_iso": slot_end.isoformat(),
            "available": True,
        })
        current = slot_end

    return slots


def generate_ics(appointment: dict) -> str:
    """Generate an .ics calendar file for an appointment.

    Args:
        appointment: Dict with keys: datetime (ISO str), duration_minutes,
                     case_ref, client_name, type, notes.

    Returns:
        String containing the .ics file content.
    """
    dt_str = appointment.get("datetime", "")
    duration = appointment.get("duration_minutes", 60)
    case_ref = appointment.get("case_ref", "")
    client_name = appointment.get("client_name", "")
    appt_type = appointment.get("type", "consultation")
    notes = appointment.get("notes", "") or ""

    dt_start = datetime.fromisoformat(dt_str)
    dt_end = dt_start + timedelta(minutes=duration)

    dtstart = dt_start.strftime("%Y%m%dT%H%M%S")
    dtend = dt_end.strftime("%Y%m%dT%H%M%S")
    dtstamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    uid = f"{case_ref}-{dtstart}@immigration-portal"

    summary = f"Immigration {appt_type.title()} — {client_name}"
    description = f"Case: {case_ref}\\nType: {appt_type}\\n{notes}".replace("\n", "\\n")

    return dedent(f"""\
        BEGIN:VCALENDAR
        VERSION:2.0
        PRODID:-//MonoClaw Immigration//EN
        BEGIN:VEVENT
        UID:{uid}
        DTSTAMP:{dtstamp}
        DTSTART;TZID=Asia/Hong_Kong:{dtstart}
        DTEND;TZID=Asia/Hong_Kong:{dtend}
        SUMMARY:{summary}
        DESCRIPTION:{description}
        STATUS:CONFIRMED
        END:VEVENT
        END:VCALENDAR""")


def _parse_hours(hours_str: str) -> tuple[dt_time, dt_time]:
    """Parse "HH:MM-HH:MM" into (open_time, close_time)."""
    parts = hours_str.split("-")
    if len(parts) != 2:
        return dt_time(9, 0), dt_time(18, 0)

    open_parts = parts[0].strip().split(":")
    close_parts = parts[1].strip().split(":")

    open_time = dt_time(int(open_parts[0]), int(open_parts[1]))
    close_time = dt_time(int(close_parts[0]), int(close_parts[1]))

    return open_time, close_time
