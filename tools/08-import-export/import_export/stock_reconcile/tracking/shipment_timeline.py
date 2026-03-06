"""Shipment event timeline — tracks milestones from creation to close."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from openclaw_shared.database import get_db


TIMELINE_SCHEMA = """
CREATE TABLE IF NOT EXISTS shipment_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    shipment_id INTEGER REFERENCES shipments(id),
    event_type TEXT NOT NULL,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""


class ShipmentTimeline:
    """Records and retrieves ordered events for a shipment's lifecycle."""

    EVENT_TYPES = (
        "created", "manifest_uploaded", "receipt_uploaded",
        "reconciliation_started", "reconciliation_completed",
        "discrepancy_found", "claim_generated", "status_changed", "closed",
    )

    @staticmethod
    def ensure_table(db_path: str) -> None:
        with get_db(db_path) as conn:
            conn.executescript(TIMELINE_SCHEMA)

    @classmethod
    def get_timeline(cls, db_path: str, shipment_id: int) -> list[dict[str, Any]]:
        cls.ensure_table(db_path)
        with get_db(db_path) as conn:
            rows = conn.execute(
                """SELECT id, shipment_id, event_type, description, created_at
                   FROM shipment_events
                   WHERE shipment_id = ?
                   ORDER BY created_at ASC, id ASC""",
                (shipment_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    @classmethod
    def add_event(
        cls,
        db_path: str,
        shipment_id: int,
        event_type: str,
        description: str,
    ) -> dict[str, Any]:
        cls.ensure_table(db_path)

        with get_db(db_path) as conn:
            shipment = conn.execute(
                "SELECT id FROM shipments WHERE id = ?", (shipment_id,)
            ).fetchone()
            if not shipment:
                raise ValueError(f"Shipment {shipment_id} not found")

            cursor = conn.execute(
                """INSERT INTO shipment_events (shipment_id, event_type, description)
                   VALUES (?, ?, ?)""",
                (shipment_id, event_type, description),
            )
            event_id = cursor.lastrowid

        return {
            "event_id": event_id,
            "shipment_id": shipment_id,
            "event_type": event_type,
            "description": description,
            "created_at": datetime.now().isoformat(),
        }
