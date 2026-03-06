"""Customer database CRUD with HK phone-number deduplication."""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path
from typing import Any

from openclaw_shared.database import get_db

_HK_PHONE_RE = re.compile(r"^\+?852?(\d{8})$")


def _normalise_phone(phone: str) -> str:
    """Strip country code / leading plus to get a bare 8-digit HK number."""
    digits = re.sub(r"[^\d]", "", phone)
    if digits.startswith("852") and len(digits) == 11:
        return digits[3:]
    return digits[-8:] if len(digits) >= 8 else digits


def get_customers(
    db_path: str | Path,
    search: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """List customers, optionally filtering by name / phone substring."""
    if search:
        like = f"%{search}%"
        query = """
            SELECT * FROM customers
            WHERE name LIKE ? OR name_tc LIKE ? OR phone LIKE ?
            ORDER BY last_visit DESC NULLS LAST
            LIMIT ?
        """
        params: tuple[Any, ...] = (like, like, like, limit)
    else:
        query = "SELECT * FROM customers ORDER BY last_visit DESC NULLS LAST LIMIT ?"
        params = (limit,)

    with get_db(db_path) as conn:
        rows = conn.execute(query, params).fetchall()
    return [dict(r) for r in rows]


def get_customer(db_path: str | Path, customer_id: int) -> dict[str, Any] | None:
    """Return a single customer by ID."""
    with get_db(db_path) as conn:
        row = conn.execute("SELECT * FROM customers WHERE id = ?", (customer_id,)).fetchone()
    return dict(row) if row else None


def upsert_customer(
    db_path: str | Path,
    phone: str,
    name: str = "",
    name_tc: str = "",
) -> dict[str, Any]:
    """Insert a new customer or return existing by normalised phone.

    Deduplicates on the 8-digit HK phone number.
    """
    norm = _normalise_phone(phone)
    with get_db(db_path) as conn:
        existing = conn.execute(
            "SELECT * FROM customers WHERE phone = ?", (norm,)
        ).fetchone()
        if existing:
            if name or name_tc:
                updates: list[str] = []
                params: list[Any] = []
                if name:
                    updates.append("name = ?")
                    params.append(name)
                if name_tc:
                    updates.append("name_tc = ?")
                    params.append(name_tc)
                params.append(norm)
                conn.execute(
                    f"UPDATE customers SET {', '.join(updates)} WHERE phone = ?",
                    params,
                )
                row = conn.execute("SELECT * FROM customers WHERE phone = ?", (norm,)).fetchone()
                return dict(row)
            return dict(existing)

        conn.execute(
            """INSERT INTO customers (phone, name, name_tc, last_visit)
               VALUES (?, ?, ?, ?)""",
            (norm, name, name_tc, date.today().isoformat()),
        )
        row = conn.execute("SELECT * FROM customers WHERE phone = ?", (norm,)).fetchone()
    return dict(row)


def merge_pos_customer(
    db_path: str | Path,
    phone: str,
    sale_amount: float,
) -> dict[str, Any]:
    """Upsert customer from a POS sale — increment visit count and total spend."""
    norm = _normalise_phone(phone)
    today = date.today().isoformat()

    with get_db(db_path) as conn:
        existing = conn.execute(
            "SELECT * FROM customers WHERE phone = ?", (norm,)
        ).fetchone()

        if existing:
            conn.execute(
                """UPDATE customers
                   SET total_spend = total_spend + ?,
                       visit_count = visit_count + 1,
                       last_visit = ?
                   WHERE phone = ?""",
                (sale_amount, today, norm),
            )
        else:
            conn.execute(
                """INSERT INTO customers (phone, total_spend, visit_count, last_visit)
                   VALUES (?, ?, 1, ?)""",
                (norm, sale_amount, today),
            )

        row = conn.execute("SELECT * FROM customers WHERE phone = ?", (norm,)).fetchone()
    return dict(row)
