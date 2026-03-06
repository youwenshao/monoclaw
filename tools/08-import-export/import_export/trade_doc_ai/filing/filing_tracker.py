"""Track filing deadlines and statuses for trade declarations."""

from __future__ import annotations

import logging
from pathlib import Path

from openclaw_shared.database import get_db

logger = logging.getLogger("openclaw.trade-doc-ai.filing-tracker")


class FilingTracker:
    """Monitor TDEC filing deadlines and manage status transitions."""

    def get_pending_filings(self, db_path: str | Path) -> list[dict]:
        """Get declarations that are approaching their filing deadline.

        Returns drafts whose deadline is within the next 7 days.
        """
        with get_db(db_path) as conn:
            rows = conn.execute(
                """SELECT td.*,
                          julianday(td.filing_deadline) - julianday('now') AS days_remaining,
                          (SELECT COUNT(*) FROM declaration_items WHERE declaration_id = td.id) AS item_count
                   FROM trade_declarations td
                   WHERE td.filing_status = 'draft'
                     AND td.filing_deadline IS NOT NULL
                     AND td.filing_deadline >= date('now')
                     AND td.filing_deadline <= date('now', '+7 days')
                   ORDER BY td.filing_deadline ASC"""
            ).fetchall()
        return [dict(r) for r in rows]

    def get_overdue_filings(self, db_path: str | Path) -> list[dict]:
        """Get declarations that have passed their filing deadline without being filed."""
        with get_db(db_path) as conn:
            rows = conn.execute(
                """SELECT td.*,
                          julianday('now') - julianday(td.filing_deadline) AS days_overdue,
                          (SELECT COUNT(*) FROM declaration_items WHERE declaration_id = td.id) AS item_count
                   FROM trade_declarations td
                   WHERE td.filing_status = 'draft'
                     AND td.filing_deadline IS NOT NULL
                     AND td.filing_deadline < date('now')
                   ORDER BY td.filing_deadline ASC"""
            ).fetchall()
        return [dict(r) for r in rows]

    def get_all_filings(self, db_path: str | Path) -> list[dict]:
        """Get all declarations with their filing status and deadline info."""
        with get_db(db_path) as conn:
            rows = conn.execute(
                """SELECT td.*,
                          CASE
                            WHEN td.filing_status != 'draft' THEN 'filed'
                            WHEN td.filing_deadline < date('now') THEN 'overdue'
                            WHEN td.filing_deadline <= date('now', '+3 days') THEN 'urgent'
                            WHEN td.filing_deadline <= date('now', '+7 days') THEN 'upcoming'
                            ELSE 'on_track'
                          END AS urgency,
                          julianday(td.filing_deadline) - julianday('now') AS days_remaining,
                          (SELECT COUNT(*) FROM declaration_items WHERE declaration_id = td.id) AS item_count
                   FROM trade_declarations td
                   ORDER BY
                     CASE td.filing_status
                       WHEN 'draft' THEN 0
                       WHEN 'filed' THEN 1
                       WHEN 'accepted' THEN 2
                       WHEN 'rejected' THEN 0
                       ELSE 3
                     END,
                     td.filing_deadline ASC"""
            ).fetchall()
        return [dict(r) for r in rows]

    def update_status(
        self,
        db_path: str | Path,
        declaration_id: int,
        status: str,
        response: dict,
    ) -> dict:
        """Update a declaration's filing status and log the event.

        Valid statuses: draft, filed, accepted, rejected, amended.
        The response dict is stored in filing_history for audit.
        """
        valid_statuses = {"draft", "filed", "accepted", "rejected", "amended"}
        if status not in valid_statuses:
            raise ValueError(f"Invalid status: {status}. Must be one of {valid_statuses}")

        with get_db(db_path) as conn:
            row = conn.execute(
                "SELECT * FROM trade_declarations WHERE id = ?", (declaration_id,)
            ).fetchone()
            if not row:
                raise ValueError(f"Declaration {declaration_id} not found")

            conn.execute(
                """UPDATE trade_declarations
                   SET filing_status = ?,
                       filed_date = CASE WHEN ? IN ('filed','accepted') THEN CURRENT_TIMESTAMP ELSE filed_date END
                   WHERE id = ?""",
                (status, status, declaration_id),
            )

            conn.execute(
                """INSERT INTO filing_history
                   (declaration_id, action, provider, response_code, response_message)
                   VALUES (?, ?, ?, ?, ?)""",
                (
                    declaration_id,
                    f"status_change_to_{status}",
                    response.get("provider", "tradelink"),
                    response.get("reference", ""),
                    response.get("message", ""),
                ),
            )

            updated = conn.execute(
                "SELECT * FROM trade_declarations WHERE id = ?", (declaration_id,)
            ).fetchone()

        logger.info("Updated declaration %d status to %s", declaration_id, status)
        return dict(updated)
