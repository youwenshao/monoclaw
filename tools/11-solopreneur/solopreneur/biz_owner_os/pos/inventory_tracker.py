"""Inventory monitoring — low-stock detection and stock adjustments."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from openclaw_shared.database import get_db


def get_low_stock_items(
    db_path: str | Path,
    threshold_override: int | None = None,
) -> list[dict[str, Any]]:
    """Return items whose current stock is at or below their threshold.

    If *threshold_override* is given it replaces each item's own
    ``low_stock_threshold`` for the comparison.
    """
    if threshold_override is not None:
        query = """
            SELECT * FROM inventory
            WHERE current_stock <= ?
            ORDER BY current_stock ASC
        """
        params: tuple[Any, ...] = (threshold_override,)
    else:
        query = """
            SELECT * FROM inventory
            WHERE current_stock <= low_stock_threshold
            ORDER BY current_stock ASC
        """
        params = ()

    with get_db(db_path) as conn:
        rows = conn.execute(query, params).fetchall()
    return [dict(r) for r in rows]


def update_stock(
    db_path: str | Path,
    item_id: int,
    quantity_change: int,
) -> dict[str, Any]:
    """Adjust stock by *quantity_change* (positive = restock, negative = sold/waste).

    Returns the updated item row.
    """
    now = datetime.now().isoformat()
    with get_db(db_path) as conn:
        conn.execute(
            """UPDATE inventory
               SET current_stock = current_stock + ?,
                   last_updated = ?
               WHERE id = ?""",
            (quantity_change, now, item_id),
        )
        row = conn.execute("SELECT * FROM inventory WHERE id = ?", (item_id,)).fetchone()
    if row is None:
        return {}
    return dict(row)


def get_inventory_summary(db_path: str | Path) -> dict[str, Any]:
    """High-level inventory stats: total items, low-stock count, total value."""
    with get_db(db_path) as conn:
        total = conn.execute("SELECT COUNT(*) FROM inventory").fetchone()[0]
        low = conn.execute(
            "SELECT COUNT(*) FROM inventory WHERE current_stock <= low_stock_threshold"
        ).fetchone()[0]
        value_row = conn.execute(
            "SELECT COALESCE(SUM(current_stock * unit_cost), 0) AS total_value FROM inventory"
        ).fetchone()
        items = [dict(r) for r in conn.execute(
            "SELECT * FROM inventory ORDER BY item_name"
        ).fetchall()]

    return {
        "total_items": total,
        "low_stock_count": low,
        "total_inventory_value": round(value_row["total_value"], 2),
        "items": items,
    }
