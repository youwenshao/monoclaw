"""CFI / DCT procedural deadline rules.

Encodes the standard procedural timeline for civil actions in the
Court of First Instance (RHC) and the District Court (RDC).
All calendar-day offsets are measured from the trigger event date and
rolled forward if they land on a non-business day.
"""

from __future__ import annotations

from datetime import date

from legal.deadline_guardian.business_days import add_calendar_days_with_rollover

# Each rule tuple: (deadline_type, human description, calendar_days, statutory_basis)

CFI_RULES: dict[str, list[tuple[str, str, int, str]]] = {
    "writ_issued": [
        ("AoS", "Acknowledgment of Service", 14, "RHC O.12 r.4"),
        ("Defence", "Filing of Defence", 42, "RHC O.18 r.2"),
        ("Close of Pleadings", "Close of Pleadings", 56, "RHC O.18 r.20"),
        ("SFD", "Summons for Directions", 86, "RHC O.25 r.1"),
    ],
    "aos_filed": [
        ("Defence", "Filing of Defence", 28, "RHC O.18 r.2"),
        ("Close of Pleadings", "Close of Pleadings", 42, "RHC O.18 r.20"),
        ("SFD", "Summons for Directions", 72, "RHC O.25 r.1"),
    ],
    "defence_filed": [
        ("Close of Pleadings", "Close of Pleadings", 14, "RHC O.18 r.20"),
        ("SFD", "Summons for Directions", 44, "RHC O.25 r.1"),
    ],
    "close_of_pleadings": [
        ("SFD", "Summons for Directions", 30, "RHC O.25 r.1"),
    ],
    "sfd_heard": [
        ("Discovery", "List of Documents", 28, "RHC O.24 r.2"),
        ("Witness Statements", "Exchange of Witness Statements", 56, "RHC O.38 r.2A"),
        ("Set Down", "Set Down for Trial", 180, "RHC O.34 r.1"),
    ],
}

DCT_RULES: dict[str, list[tuple[str, str, int, str]]] = {
    "writ_issued": [
        ("AoS", "Acknowledgment of Service", 14, "RDC O.12 r.4"),
        ("Defence", "Filing of Defence", 42, "RDC O.18 r.2"),
        ("Close of Pleadings", "Close of Pleadings", 56, "RDC O.18 r.20"),
        ("Checklist Questionnaire", "Filing of Checklist Questionnaire", 70, "RDC O.25 r.1(1A)"),
    ],
    "aos_filed": [
        ("Defence", "Filing of Defence", 28, "RDC O.18 r.2"),
        ("Close of Pleadings", "Close of Pleadings", 42, "RDC O.18 r.20"),
        ("Checklist Questionnaire", "Filing of Checklist Questionnaire", 56, "RDC O.25 r.1(1A)"),
    ],
    "defence_filed": [
        ("Close of Pleadings", "Close of Pleadings", 14, "RDC O.18 r.20"),
        ("Checklist Questionnaire", "Filing of Checklist Questionnaire", 28, "RDC O.25 r.1(1A)"),
    ],
    "close_of_pleadings": [
        ("Checklist Questionnaire", "Filing of Checklist Questionnaire", 14, "RDC O.25 r.1(1A)"),
    ],
    "checklist_filed": [
        ("Discovery", "List of Documents", 28, "RDC O.24 r.2"),
        ("Witness Statements", "Exchange of Witness Statements", 56, "RDC O.38 r.2A"),
        ("Pre-trial Review", "Pre-trial Review Hearing", 90, "RDC O.34A"),
    ],
}

COURT_RULES: dict[str, dict[str, list[tuple[str, str, int, str]]]] = {
    "CFI": CFI_RULES,
    "DCT": DCT_RULES,
}


def calculate_procedural_deadlines(
    trigger_event: str,
    trigger_date: date,
    court: str,
    holidays: list[str] | None = None,
) -> list[dict]:
    """Calculate downstream procedural deadlines for a trigger event.

    Parameters
    ----------
    trigger_event : str
        One of the recognised trigger keys (e.g. ``"writ_issued"``).
    trigger_date : date
        Date the trigger event occurred.
    court : str
        ``"CFI"`` or ``"DCT"``.
    holidays : list[str] | None
        ISO-format holiday dates; ``None`` uses built-in HK defaults.

    Returns
    -------
    list[dict]
        Sorted by ``due_date``.  Each dict contains *deadline_type*,
        *description*, *due_date*, *trigger_date*, *calendar_days*,
        *statutory_basis*, *court*, and *days_remaining*.
    """
    rules = COURT_RULES.get(court)
    if rules is None:
        raise ValueError(
            f"Unsupported court '{court}'. Supported: {', '.join(COURT_RULES)}"
        )

    event_rules = rules.get(trigger_event)
    if event_rules is None:
        available = ", ".join(rules.keys())
        raise ValueError(
            f"Unknown trigger event '{trigger_event}' for {court}. "
            f"Available: {available}"
        )

    deadlines: list[dict] = []
    for dtype, description, cal_days, basis in event_rules:
        due = add_calendar_days_with_rollover(trigger_date, cal_days, holidays)
        days_remaining = (due - date.today()).days
        deadlines.append({
            "deadline_type": dtype,
            "description": description,
            "due_date": due.isoformat(),
            "trigger_date": trigger_date.isoformat(),
            "calendar_days": cal_days,
            "statutory_basis": basis,
            "court": court,
            "days_remaining": days_remaining,
        })

    deadlines.sort(key=lambda d: d["due_date"])
    return deadlines
