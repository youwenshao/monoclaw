"""Insurance claim lifecycle tracker."""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from openclaw_shared.database import get_db

logger = logging.getLogger("openclaw.medical-dental.insurance.claims")

VALID_STATUSES = frozenset({
    "pending", "submitted", "approved", "partial", "rejected", "paid", "appealed",
})

ALLOWED_TRANSITIONS: dict[str, frozenset[str]] = {
    "pending": frozenset({"submitted"}),
    "submitted": frozenset({"approved", "partial", "rejected"}),
    "approved": frozenset({"paid"}),
    "partial": frozenset({"paid", "appealed"}),
    "rejected": frozenset({"appealed"}),
    "appealed": frozenset({"approved", "partial", "rejected"}),
    "paid": frozenset(),
}


class ClaimTracker:
    """Manage insurance claims against the SQLite database."""

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = db_path

    def create_claim(self, data: dict[str, Any]) -> int:
        """Insert a new claim record. Returns the new claim ID."""
        with get_db(self.db_path) as conn:
            cursor = conn.execute(
                """INSERT INTO claims
                   (patient_id, policy_id, claim_date, procedure_code, description,
                    billed_amount, status)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    data.get("patient_id"),
                    data.get("policy_id"),
                    data.get("claim_date", date.today().isoformat()),
                    data.get("procedure_code", ""),
                    data.get("description", ""),
                    data.get("billed_amount", 0),
                    data.get("status", "pending"),
                ),
            )
            claim_id = cursor.lastrowid
        logger.info("Created claim %d for patient %s", claim_id, data.get("patient_id"))
        return claim_id  # type: ignore[return-value]

    def update_claim(self, claim_id: int, **kwargs: Any) -> dict[str, Any]:
        """Update claim fields. Validates status transitions if status is changed."""
        with get_db(self.db_path) as conn:
            row = conn.execute("SELECT * FROM claims WHERE id = ?", (claim_id,)).fetchone()
            if not row:
                raise ValueError(f"Claim {claim_id} not found")

            current = dict(row)

            new_status = kwargs.get("status")
            if new_status:
                if new_status not in VALID_STATUSES:
                    raise ValueError(f"Invalid status: {new_status}")
                allowed = ALLOWED_TRANSITIONS.get(current["status"], frozenset())
                if new_status not in allowed:
                    raise ValueError(
                        f"Cannot transition from '{current['status']}' to '{new_status}'. "
                        f"Allowed: {sorted(allowed)}"
                    )

            allowed_fields = {
                "status", "approved_amount", "patient_copay", "insurer_reference",
                "submitted_at", "resolved_at", "description", "billed_amount",
            }
            updates: list[str] = []
            params: list[Any] = []
            for field, value in kwargs.items():
                if field not in allowed_fields:
                    continue
                updates.append(f"{field} = ?")
                params.append(value)

            if new_status == "submitted" and "submitted_at" not in kwargs:
                updates.append("submitted_at = ?")
                params.append(datetime.now().isoformat())

            if new_status in ("approved", "partial", "rejected", "paid") and "resolved_at" not in kwargs:
                updates.append("resolved_at = ?")
                params.append(datetime.now().isoformat())

            if not updates:
                return current

            params.append(claim_id)
            conn.execute(
                f"UPDATE claims SET {', '.join(updates)} WHERE id = ?",
                params,
            )

            updated = conn.execute("SELECT * FROM claims WHERE id = ?", (claim_id,)).fetchone()

        logger.info("Updated claim %d: %s", claim_id, list(kwargs.keys()))
        return dict(updated)  # type: ignore[arg-type]

    def get_by_id(self, claim_id: int) -> dict[str, Any] | None:
        with get_db(self.db_path) as conn:
            row = conn.execute("SELECT * FROM claims WHERE id = ?", (claim_id,)).fetchone()
        return dict(row) if row else None

    def get_by_status(self, status: str) -> list[dict[str, Any]]:
        """Return all claims with the given status."""
        with get_db(self.db_path) as conn:
            rows = conn.execute(
                "SELECT * FROM claims WHERE status = ? ORDER BY created_at DESC",
                (status,),
            ).fetchall()
        return [dict(r) for r in rows]

    def get_overdue(self, days: int = 30) -> list[dict[str, Any]]:
        """Return submitted claims older than `days` without resolution."""
        cutoff = (date.today() - timedelta(days=days)).isoformat()
        with get_db(self.db_path) as conn:
            rows = conn.execute(
                "SELECT * FROM claims "
                "WHERE status = 'submitted' AND submitted_at <= ? "
                "ORDER BY submitted_at ASC",
                (cutoff,),
            ).fetchall()
        return [dict(r) for r in rows]

    def get_patient_claims(self, patient_id: int) -> list[dict[str, Any]]:
        """Return all claims for a specific patient."""
        with get_db(self.db_path) as conn:
            rows = conn.execute(
                "SELECT * FROM claims WHERE patient_id = ? ORDER BY claim_date DESC",
                (patient_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    def list_all(self, status: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        """List claims with optional status filter."""
        with get_db(self.db_path) as conn:
            if status:
                rows = conn.execute(
                    "SELECT * FROM claims WHERE status = ? ORDER BY created_at DESC LIMIT ?",
                    (status, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM claims ORDER BY created_at DESC LIMIT ?",
                    (limit,),
                ).fetchall()
        return [dict(r) for r in rows]

    def get_summary(self) -> dict[str, Any]:
        """Return aggregate claim statistics."""
        with get_db(self.db_path) as conn:
            total = conn.execute("SELECT COUNT(*) FROM claims").fetchone()[0]
            by_status = {}
            for row in conn.execute(
                "SELECT status, COUNT(*) as cnt, COALESCE(SUM(billed_amount),0) as total_billed "
                "FROM claims GROUP BY status"
            ).fetchall():
                r = dict(row)
                by_status[r["status"]] = {"count": r["cnt"], "total_billed": r["total_billed"]}

            total_approved = conn.execute(
                "SELECT COALESCE(SUM(approved_amount), 0) FROM claims WHERE approved_amount IS NOT NULL"
            ).fetchone()[0]

        return {
            "total_claims": total,
            "by_status": by_status,
            "total_approved_amount": total_approved,
        }
