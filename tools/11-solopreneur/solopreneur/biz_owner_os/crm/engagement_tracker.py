"""Customer engagement scoring and segmentation."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
from typing import Any

from openclaw_shared.database import get_db


def get_engagement_score(db_path: str | Path, customer_id: int) -> dict[str, Any]:
    """Compute a 0–100 engagement score based on recency, frequency, and monetary.

    Weights: recency 40 %, frequency 30 %, monetary 30 %.
    """
    with get_db(db_path) as conn:
        cust = conn.execute(
            "SELECT * FROM customers WHERE id = ?", (customer_id,)
        ).fetchone()
        if not cust:
            return {"customer_id": customer_id, "score": 0, "tier": "unknown"}

        cust = dict(cust)

        max_spend = conn.execute(
            "SELECT MAX(total_spend) AS m FROM customers"
        ).fetchone()["m"] or 1
        max_visits = conn.execute(
            "SELECT MAX(visit_count) AS m FROM customers"
        ).fetchone()["m"] or 1

    # Recency score (days since last visit, max 90 days window)
    last_visit = cust.get("last_visit")
    if last_visit:
        try:
            days_ago = (date.today() - date.fromisoformat(str(last_visit))).days
        except (ValueError, TypeError):
            days_ago = 90
    else:
        days_ago = 90
    recency = max(0, 100 - (days_ago / 90) * 100)

    # Frequency score
    frequency = min(100, (cust.get("visit_count", 0) / max_visits) * 100)

    # Monetary score
    monetary = min(100, (cust.get("total_spend", 0) / max_spend) * 100)

    score = round(recency * 0.4 + frequency * 0.3 + monetary * 0.3, 1)

    if score >= 70:
        tier = "vip"
    elif score >= 40:
        tier = "regular"
    elif score > 0:
        tier = "occasional"
    else:
        tier = "inactive"

    return {
        "customer_id": customer_id,
        "score": score,
        "tier": tier,
        "recency_score": round(recency, 1),
        "frequency_score": round(frequency, 1),
        "monetary_score": round(monetary, 1),
    }


def get_top_customers(db_path: str | Path, limit: int = 20) -> list[dict[str, Any]]:
    """Return top customers ranked by total spend."""
    with get_db(db_path) as conn:
        rows = conn.execute(
            """SELECT * FROM customers
               WHERE total_spend > 0
               ORDER BY total_spend DESC
               LIMIT ?""",
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]


def get_customer_segments(db_path: str | Path) -> dict[str, Any]:
    """Segment all customers into VIP / Regular / Occasional / Inactive buckets."""
    with get_db(db_path) as conn:
        customers = conn.execute("SELECT * FROM customers").fetchall()

    if not customers:
        return {"vip": [], "regular": [], "occasional": [], "inactive": [], "counts": {}}

    customers = [dict(r) for r in customers]

    max_spend = max((c.get("total_spend", 0) for c in customers), default=1) or 1
    max_visits = max((c.get("visit_count", 0) for c in customers), default=1) or 1

    segments: dict[str, list[dict[str, Any]]] = {
        "vip": [],
        "regular": [],
        "occasional": [],
        "inactive": [],
    }

    for c in customers:
        last_visit = c.get("last_visit")
        if last_visit:
            try:
                days_ago = (date.today() - date.fromisoformat(str(last_visit))).days
            except (ValueError, TypeError):
                days_ago = 90
        else:
            days_ago = 90

        recency = max(0, 100 - (days_ago / 90) * 100)
        frequency = min(100, (c.get("visit_count", 0) / max_visits) * 100)
        monetary = min(100, (c.get("total_spend", 0) / max_spend) * 100)
        score = round(recency * 0.4 + frequency * 0.3 + monetary * 0.3, 1)

        if score >= 70:
            segments["vip"].append(c)
        elif score >= 40:
            segments["regular"].append(c)
        elif score > 0:
            segments["occasional"].append(c)
        else:
            segments["inactive"].append(c)

    return {
        **segments,
        "counts": {k: len(v) for k, v in segments.items()},
    }
