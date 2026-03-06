"""Contractor CRUD operations."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from openclaw_shared.database import get_db

logger = logging.getLogger("openclaw.construction.defects_manager.contractors.database")


def get_contractors(
    db_path: str | Path,
    trade: str | None = None,
) -> list[dict[str, Any]]:
    """Return active contractors, optionally filtered by trade specialty."""
    with get_db(db_path) as conn:
        if trade:
            rows = conn.execute(
                "SELECT * FROM contractors WHERE active = TRUE ORDER BY company_name"
            ).fetchall()
            results = []
            for row in rows:
                contractor = dict(row)
                trades = _parse_trades(contractor.get("trades"))
                if trade.lower() in trades:
                    results.append(contractor)
            return results

        rows = conn.execute(
            "SELECT * FROM contractors WHERE active = TRUE ORDER BY company_name"
        ).fetchall()
        return [dict(r) for r in rows]


def get_contractor(db_path: str | Path, contractor_id: int) -> dict[str, Any] | None:
    """Return a single contractor by ID, or ``None`` if not found."""
    with get_db(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM contractors WHERE id = ?", (contractor_id,)
        ).fetchone()
        return dict(row) if row else None


def update_contractor(db_path: str | Path, contractor_id: int, **kwargs: Any) -> None:
    """Update contractor fields.

    Accepts any column name as a keyword argument. Unknown keys are
    silently ignored.
    """
    allowed = {
        "company_name", "contact_person", "phone", "email",
        "trades", "registration_numbers", "hourly_rate", "active",
        "response_time_score", "quality_score", "cost_score",
        "communication_score", "performance_score",
    }
    updates: list[str] = []
    params: list[Any] = []
    for key, value in kwargs.items():
        if key in allowed:
            updates.append(f"{key} = ?")
            params.append(value)

    if not updates:
        logger.debug("No valid fields to update for contractor #%d", contractor_id)
        return

    params.append(contractor_id)
    with get_db(db_path) as conn:
        conn.execute(
            f"UPDATE contractors SET {', '.join(updates)} WHERE id = ?",
            params,
        )
    logger.info("Contractor #%d updated: %s", contractor_id, ", ".join(kwargs.keys()))


def create_contractor(
    db_path: str | Path,
    company_name: str,
    *,
    contact_person: str = "",
    phone: str = "",
    email: str = "",
    trades: list[str] | None = None,
    registration_numbers: str = "",
    hourly_rate: float | None = None,
) -> int:
    """Insert a new contractor and return the new ID."""
    trades_json = json.dumps(trades or [])
    with get_db(db_path) as conn:
        cursor = conn.execute(
            "INSERT INTO contractors (company_name, contact_person, phone, email, "
            "trades, registration_numbers, hourly_rate) VALUES (?,?,?,?,?,?,?)",
            (company_name, contact_person, phone, email,
             trades_json, registration_numbers, hourly_rate),
        )
        new_id: int = cursor.lastrowid  # type: ignore[assignment]
    logger.info("Contractor #%d created: %s", new_id, company_name)
    return new_id


def _parse_trades(raw: str | None) -> list[str]:
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
        return [t.lower() for t in parsed] if isinstance(parsed, list) else []
    except (json.JSONDecodeError, TypeError):
        return [t.strip().lower() for t in raw.split(",") if t.strip()]
