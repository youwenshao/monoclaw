"""Query recent comparable transactions from the local SQLite database."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from openclaw_shared.database import get_db

logger = logging.getLogger(__name__)


def get_comparable_transactions(
    db_path: str | Path,
    *,
    district: str | None = None,
    days: int = 90,
) -> list[dict[str, Any]]:
    """Return transactions from the last *days* days, optionally filtered by district."""
    conditions = ["date >= date('now', ?)"  ]
    params: list[Any] = [f"-{days} days"]

    if district:
        conditions.append("district = ?")
        params.append(district)

    sql = (
        "SELECT * FROM transactions "
        f"WHERE {' AND '.join(conditions)} "
        "ORDER BY date DESC"
    )

    with get_db(db_path) as conn:
        rows = conn.execute(sql, params).fetchall()

    return [dict(r) for r in rows]
