"""Employee CRUD operations for the MPF module."""

from __future__ import annotations

from datetime import date
from typing import Any

from openclaw_shared.database import get_db

from solopreneur.mpf_calc.calculation.employee_classifier import get_mpf_enrollment_date


def list_employees(db_path: str, active_only: bool = True) -> list[dict[str, Any]]:
    """Return all employees, optionally filtered to active only."""
    with get_db(db_path) as conn:
        query = "SELECT * FROM employees"
        if active_only:
            query += " WHERE active = 1"
        query += " ORDER BY name_en"
        return [dict(r) for r in conn.execute(query).fetchall()]


def get_employee(db_path: str, employee_id: int) -> dict[str, Any]:
    """Fetch a single employee by id."""
    with get_db(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM employees WHERE id = ?", (employee_id,)
        ).fetchone()
    if row is None:
        raise ValueError(f"Employee {employee_id} not found")
    return dict(row)


def create_employee(db_path: str, data: dict[str, Any]) -> dict[str, Any]:
    """Insert a new employee record and return the created row."""
    start_date_str = data.get("start_date", date.today().isoformat())
    start_date = date.fromisoformat(start_date_str)
    enrollment = data.get(
        "mpf_enrollment_date",
        get_mpf_enrollment_date(start_date).isoformat(),
    )

    with get_db(db_path) as conn:
        cursor = conn.execute(
            """INSERT INTO employees
               (name_en, name_tc, hkid_last4, employment_type, start_date,
                mpf_enrollment_date, mpf_scheme, mpf_member_number,
                monthly_salary, active)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1)""",
            (
                data["name_en"],
                data.get("name_tc", ""),
                data.get("hkid_last4", ""),
                data.get("employment_type", "full_time"),
                start_date_str,
                enrollment,
                data.get("mpf_scheme", ""),
                data.get("mpf_member_number", ""),
                float(data.get("monthly_salary", 0)),
            ),
        )
        new_id = cursor.lastrowid
        row = conn.execute(
            "SELECT * FROM employees WHERE id = ?", (new_id,)
        ).fetchone()
    return dict(row)


def update_employee(
    db_path: str, employee_id: int, data: dict[str, Any]
) -> dict[str, Any]:
    """Update mutable fields on an employee record."""
    allowed = {
        "name_en",
        "name_tc",
        "hkid_last4",
        "employment_type",
        "start_date",
        "mpf_enrollment_date",
        "mpf_scheme",
        "mpf_member_number",
        "monthly_salary",
        "active",
    }
    fields = {k: v for k, v in data.items() if k in allowed}
    if not fields:
        return get_employee(db_path, employee_id)

    set_clause = ", ".join(f"{k} = ?" for k in fields)
    values = list(fields.values()) + [employee_id]

    with get_db(db_path) as conn:
        conn.execute(
            f"UPDATE employees SET {set_clause} WHERE id = ?",  # noqa: S608
            values,
        )
        row = conn.execute(
            "SELECT * FROM employees WHERE id = ?", (employee_id,)
        ).fetchone()
    if row is None:
        raise ValueError(f"Employee {employee_id} not found")
    return dict(row)


def deactivate_employee(db_path: str, employee_id: int) -> None:
    """Soft-delete by setting active = FALSE."""
    with get_db(db_path) as conn:
        conn.execute(
            "UPDATE employees SET active = 0 WHERE id = ?", (employee_id,)
        )
