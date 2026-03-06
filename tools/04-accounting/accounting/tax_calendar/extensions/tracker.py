"""Extension tracking for tax filing deadlines."""

from __future__ import annotations

import logging
from datetime import date
from pathlib import Path
from typing import Any

from openclaw_shared.database import get_db

logger = logging.getLogger("openclaw.accounting.tax_calendar.extensions")

EXTENSION_TYPES = {
    "block": "Block extension (HKICPA negotiated)",
    "individual": "Individual extension application",
}

EXTENSION_STATUSES = ("applied", "granted", "rejected", "expired")


def record_extension(
    db_path: str | Path,
    deadline_id: int,
    extension_type: str,
    extended_due_date: date | str,
    extension_status: str = "applied",
    notes: str = "",
) -> dict[str, Any]:
    """Record or update an extension on a deadline.

    extension_type: "block" (HKICPA) or "individual"
    extension_status: "applied", "granted", "rejected", "expired"
    """
    if extension_status not in EXTENSION_STATUSES:
        raise ValueError(f"Invalid extension_status: {extension_status}. Must be one of {EXTENSION_STATUSES}")

    if isinstance(extended_due_date, str):
        extended_due_date = date.fromisoformat(extended_due_date)

    with get_db(db_path) as conn:
        row = conn.execute("SELECT * FROM deadlines WHERE id = ?", (deadline_id,)).fetchone()
        if not row:
            raise ValueError(f"Deadline {deadline_id} not found")

        dl = dict(row)
        original_due = date.fromisoformat(dl["original_due_date"]) if isinstance(dl["original_due_date"], str) else dl["original_due_date"]

        if extended_due_date <= original_due:
            raise ValueError(
                f"Extended due date ({extended_due_date}) must be after original due date ({original_due})"
            )

        conn.execute(
            """UPDATE deadlines
               SET extension_type = ?, extended_due_date = ?, extension_status = ?,
                   notes = CASE WHEN notes IS NULL OR notes = '' THEN ? ELSE notes || char(10) || ? END
               WHERE id = ?""",
            (
                extension_type,
                extended_due_date.isoformat(),
                extension_status,
                notes, notes,
                deadline_id,
            ),
        )

    logger.info(
        "Extension recorded: deadline %d, type=%s, new due=%s, status=%s",
        deadline_id, extension_type, extended_due_date, extension_status,
    )

    return {
        "deadline_id": deadline_id,
        "extension_type": extension_type,
        "extended_due_date": extended_due_date.isoformat(),
        "extension_status": extension_status,
        "original_due_date": dl["original_due_date"],
    }


def update_extension_status(
    db_path: str | Path,
    deadline_id: int,
    new_status: str,
) -> dict[str, Any]:
    """Update the status of an existing extension."""
    if new_status not in EXTENSION_STATUSES:
        raise ValueError(f"Invalid status: {new_status}. Must be one of {EXTENSION_STATUSES}")

    with get_db(db_path) as conn:
        row = conn.execute("SELECT * FROM deadlines WHERE id = ?", (deadline_id,)).fetchone()
        if not row:
            raise ValueError(f"Deadline {deadline_id} not found")

        dl = dict(row)
        if not dl.get("extension_type"):
            raise ValueError(f"Deadline {deadline_id} has no extension to update")

        conn.execute(
            "UPDATE deadlines SET extension_status = ? WHERE id = ?",
            (new_status, deadline_id),
        )

    logger.info("Extension status updated: deadline %d → %s", deadline_id, new_status)
    return {"deadline_id": deadline_id, "extension_status": new_status}


def calculate_block_extension_date(
    ird_code: str, assessment_year: str, config: dict
) -> date | None:
    """Look up or calculate the block extension date for an IRD code.

    Block extensions are negotiated annually by HKICPA and apply to
    all firms that have signed up.
    """
    ext_overrides = config.get("extra", {}).get("block_extension_dates", {})

    parts = assessment_year.split("/")
    start_year = int(parts[0])
    end_suffix = parts[1] if len(parts) > 1 else str(start_year + 1)[-2:]
    end_year = int(str(start_year)[:2] + end_suffix)

    code_key = f"{ird_code}_code"
    if code_key in ext_overrides:
        return date.fromisoformat(ext_overrides[code_key])

    defaults = {
        "D": date(end_year, 11, 15),
        "M": date(end_year + 1, 1, 15),
        "N": date(end_year, 5, 31),
    }
    return defaults.get(ird_code)


def get_extension_summary(db_path: str | Path) -> dict[str, Any]:
    """Get a summary of all extensions across all deadlines."""
    with get_db(db_path) as conn:
        total = conn.execute(
            "SELECT COUNT(*) FROM deadlines WHERE extension_type IS NOT NULL"
        ).fetchone()[0]
        by_status = {
            row[0]: row[1]
            for row in conn.execute(
                """SELECT extension_status, COUNT(*)
                   FROM deadlines
                   WHERE extension_type IS NOT NULL
                   GROUP BY extension_status"""
            ).fetchall()
        }
        by_type = {
            row[0]: row[1]
            for row in conn.execute(
                """SELECT extension_type, COUNT(*)
                   FROM deadlines
                   WHERE extension_type IS NOT NULL
                   GROUP BY extension_type"""
            ).fetchall()
        }

    return {
        "total_extensions": total,
        "by_status": by_status,
        "by_type": by_type,
    }
