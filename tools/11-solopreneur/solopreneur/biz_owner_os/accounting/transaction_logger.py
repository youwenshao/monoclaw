"""Income and expense recording with receipt storage."""

from __future__ import annotations

import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from openclaw_shared.database import get_db


def record_income(db_path: str | Path, sale_data: dict[str, Any]) -> int:
    """Insert a sale row and return the new ID."""
    with get_db(db_path) as conn:
        cursor = conn.execute(
            """INSERT INTO sales
               (pos_transaction_id, sale_date, total_amount, payment_method,
                items, customer_phone, pos_source)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                sale_data.get("pos_transaction_id", ""),
                sale_data.get("sale_date", datetime.now().isoformat()),
                float(sale_data.get("total_amount", 0)),
                sale_data.get("payment_method", "cash"),
                sale_data.get("items", ""),
                sale_data.get("customer_phone", ""),
                sale_data.get("pos_source", "manual"),
            ),
        )
        return cursor.lastrowid  # type: ignore[return-value]


def record_expense(db_path: str | Path, expense_data: dict[str, Any]) -> int:
    """Insert an expense row and return the new ID."""
    with get_db(db_path) as conn:
        cursor = conn.execute(
            """INSERT INTO expenses
               (expense_date, category, description, amount,
                receipt_photo, payment_method, recurring)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                expense_data.get("expense_date", datetime.now().date().isoformat()),
                expense_data.get("category", "other"),
                expense_data.get("description", ""),
                float(expense_data.get("amount", 0)),
                expense_data.get("receipt_photo", ""),
                expense_data.get("payment_method", "cash"),
                bool(expense_data.get("recurring", False)),
            ),
        )
        return cursor.lastrowid  # type: ignore[return-value]


def get_transactions(
    db_path: str | Path,
    start_date: str | None = None,
    end_date: str | None = None,
    category: str | None = None,
) -> dict[str, list[dict[str, Any]]]:
    """Return both income and expenses within the date range.

    Returns ``{"income": [...], "expenses": [...]}``.
    """
    income_conditions: list[str] = []
    expense_conditions: list[str] = []
    income_params: list[Any] = []
    expense_params: list[Any] = []

    if start_date:
        income_conditions.append("DATE(sale_date) >= ?")
        income_params.append(start_date)
        expense_conditions.append("expense_date >= ?")
        expense_params.append(start_date)
    if end_date:
        income_conditions.append("DATE(sale_date) <= ?")
        income_params.append(end_date)
        expense_conditions.append("expense_date <= ?")
        expense_params.append(end_date)
    if category:
        expense_conditions.append("category = ?")
        expense_params.append(category)

    income_where = f"WHERE {' AND '.join(income_conditions)}" if income_conditions else ""
    expense_where = f"WHERE {' AND '.join(expense_conditions)}" if expense_conditions else ""

    with get_db(db_path) as conn:
        income_rows = conn.execute(
            f"SELECT * FROM sales {income_where} ORDER BY sale_date DESC",
            income_params,
        ).fetchall()
        expense_rows = conn.execute(
            f"SELECT * FROM expenses {expense_where} ORDER BY expense_date DESC",
            expense_params,
        ).fetchall()

    return {
        "income": [dict(r) for r in income_rows],
        "expenses": [dict(r) for r in expense_rows],
    }


def save_receipt(workspace: str | Path, file_data: bytes, extension: str = ".jpg") -> str:
    """Persist a receipt image and return the relative path.

    Files are stored under ``<workspace>/receipts/<uuid>.<ext>``.
    """
    receipts_dir = Path(workspace) / "receipts"
    receipts_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{uuid.uuid4().hex}{extension}"
    dest = receipts_dir / filename
    dest.write_bytes(file_data)
    return str(dest.relative_to(workspace))
