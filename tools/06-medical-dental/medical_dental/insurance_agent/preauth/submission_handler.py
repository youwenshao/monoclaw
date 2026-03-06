"""Pre-authorization lifecycle tracker."""

from __future__ import annotations

import logging
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from openclaw_shared.database import get_db

logger = logging.getLogger("openclaw.medical-dental.insurance.preauth")

VALID_STATUSES = frozenset({"draft", "submitted", "approved", "denied", "expired"})

ALLOWED_TRANSITIONS: dict[str, frozenset[str]] = {
    "draft": frozenset({"submitted"}),
    "submitted": frozenset({"approved", "denied", "expired"}),
    "approved": frozenset({"expired"}),
    "denied": frozenset({"draft"}),
    "expired": frozenset({"draft"}),
}


class PreauthTracker:
    """Manage the pre-authorization lifecycle against the SQLite database."""

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = db_path

    def create_preauth(self, data: dict[str, Any]) -> int:
        """Insert a new pre-authorization record. Returns the new ID."""
        with get_db(self.db_path) as conn:
            cursor = conn.execute(
                """INSERT INTO preauthorizations
                   (patient_id, policy_id, procedure_description, estimated_cost,
                    submission_date, status, reference_number, notes)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    data.get("patient_id"),
                    data.get("policy_id"),
                    data.get("procedure_description", ""),
                    data.get("estimated_cost", 0),
                    data.get("submission_date", date.today().isoformat()),
                    data.get("status", "draft"),
                    data.get("reference_number", ""),
                    data.get("notes", ""),
                ),
            )
            preauth_id = cursor.lastrowid
        logger.info("Created preauth %d for patient %s", preauth_id, data.get("patient_id"))
        return preauth_id  # type: ignore[return-value]

    def update_status(
        self,
        preauth_id: int,
        new_status: str,
        *,
        reference_number: str | None = None,
        approved_amount: float | None = None,
        notes: str | None = None,
    ) -> dict[str, Any]:
        """Transition a pre-auth to a new status with validation."""
        if new_status not in VALID_STATUSES:
            raise ValueError(f"Invalid status: {new_status}")

        with get_db(self.db_path) as conn:
            row = conn.execute(
                "SELECT * FROM preauthorizations WHERE id = ?", (preauth_id,)
            ).fetchone()
            if not row:
                raise ValueError(f"Pre-authorization {preauth_id} not found")

            current = dict(row)
            current_status = current["status"]
            allowed = ALLOWED_TRANSITIONS.get(current_status, frozenset())
            if new_status not in allowed:
                raise ValueError(
                    f"Cannot transition from '{current_status}' to '{new_status}'. "
                    f"Allowed: {sorted(allowed)}"
                )

            updates: list[str] = ["status = ?"]
            params: list[Any] = [new_status]

            if new_status == "submitted":
                updates.append("submission_date = ?")
                params.append(date.today().isoformat())

            if new_status in ("approved", "denied"):
                updates.append("response_date = ?")
                params.append(date.today().isoformat())

            if reference_number is not None:
                updates.append("reference_number = ?")
                params.append(reference_number)

            if approved_amount is not None:
                updates.append("approved_amount = ?")
                params.append(approved_amount)

            if notes is not None:
                updates.append("notes = ?")
                params.append(notes)

            params.append(preauth_id)
            conn.execute(
                f"UPDATE preauthorizations SET {', '.join(updates)} WHERE id = ?",
                params,
            )

            updated = conn.execute(
                "SELECT * FROM preauthorizations WHERE id = ?", (preauth_id,)
            ).fetchone()

        logger.info("Preauth %d: %s -> %s", preauth_id, current_status, new_status)
        return dict(updated)  # type: ignore[arg-type]

    def get_by_id(self, preauth_id: int) -> dict[str, Any] | None:
        with get_db(self.db_path) as conn:
            row = conn.execute(
                "SELECT * FROM preauthorizations WHERE id = ?", (preauth_id,)
            ).fetchone()
        return dict(row) if row else None

    def get_pending(self) -> list[dict[str, Any]]:
        """Return all pre-auths in draft or submitted status."""
        with get_db(self.db_path) as conn:
            rows = conn.execute(
                "SELECT * FROM preauthorizations WHERE status IN ('draft', 'submitted') "
                "ORDER BY created_at DESC"
            ).fetchall()
        return [dict(r) for r in rows]

    def get_overdue(self, days: int = 5) -> list[dict[str, Any]]:
        """Return submitted pre-auths that have been waiting longer than `days`."""
        cutoff = (date.today() - timedelta(days=days)).isoformat()
        with get_db(self.db_path) as conn:
            rows = conn.execute(
                "SELECT * FROM preauthorizations "
                "WHERE status = 'submitted' AND submission_date <= ? "
                "ORDER BY submission_date ASC",
                (cutoff,),
            ).fetchall()
        return [dict(r) for r in rows]

    def list_all(self, status: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        """List pre-authorizations with optional status filter."""
        with get_db(self.db_path) as conn:
            if status:
                rows = conn.execute(
                    "SELECT * FROM preauthorizations WHERE status = ? ORDER BY created_at DESC LIMIT ?",
                    (status, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM preauthorizations ORDER BY created_at DESC LIMIT ?",
                    (limit,),
                ).fetchall()
        return [dict(r) for r in rows]
