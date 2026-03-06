"""Generate formatted daily assignment briefs for WhatsApp dispatch."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from openclaw_shared.database import get_db

logger = logging.getLogger("openclaw.construction.site_coordinator.assignment_generator")


def generate_daily_brief(
    db_path: str | Path,
    contractor_id: int,
    assignment_date: str,
) -> str:
    """Build a WhatsApp-friendly text brief for all assignments of
    *contractor_id* on *assignment_date*.
    """
    with get_db(db_path) as conn:
        contractor = conn.execute(
            "SELECT * FROM contractors WHERE id = ?", (contractor_id,)
        ).fetchone()
        if not contractor:
            return ""
        contractor = dict(contractor)

        rows = conn.execute(
            "SELECT sa.*, s.site_name, s.address, s.district, s.site_contact_name, "
            "s.site_contact_phone "
            "FROM schedule_assignments sa "
            "LEFT JOIN sites s ON sa.site_id = s.id "
            "WHERE sa.contractor_id = ? AND sa.assignment_date = ? "
            "AND sa.status NOT IN ('cancelled', 'rescheduled') "
            "ORDER BY sa.start_time",
            (contractor_id, assignment_date),
        ).fetchall()

    if not rows:
        return ""

    assignments = [dict(r) for r in rows]
    company = contractor.get("company_name", f"Contractor {contractor_id}")

    lines: list[str] = [
        f"📋 *Daily Assignment — {assignment_date}*",
        f"Contractor: {company}",
        "",
    ]

    for i, a in enumerate(assignments, 1):
        lines.append(f"*Site {i}: {a.get('site_name', 'TBC')}*")
        if a.get("address"):
            lines.append(f"📍 {a['address']}")
        if a.get("district"):
            lines.append(f"District: {a['district']}")
        lines.append(f"⏰ {a.get('start_time', '08:00')} – {a.get('end_time', '18:00')}")

        if a.get("trade"):
            lines.append(f"Trade: {a['trade']}")
        if a.get("scope_of_work"):
            lines.append(f"Scope: {a['scope_of_work']}")

        contact_name = a.get("site_contact_name", "")
        contact_phone = a.get("site_contact_phone", "")
        if contact_name or contact_phone:
            lines.append(f"👷 Site contact: {contact_name} {contact_phone}".strip())

        lines.append("")

    lines.append("Reply ✅ when completed or ❌ if unable to attend.")
    return "\n".join(lines)
