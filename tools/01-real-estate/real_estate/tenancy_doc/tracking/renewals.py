"""Renewal monitoring — upcoming renewals, alerts, and CR109 compliance."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

from openclaw_shared.database import get_db


def get_upcoming_renewals(
    db_path: str | Path,
    days_ahead: int = 90,
) -> list[dict]:
    """Return active tenancies expiring within *days_ahead* days.

    Each dict contains the tenancy row plus ``days_remaining``.
    """
    cutoff = (date.today() + timedelta(days=days_ahead)).isoformat()
    today = date.today().isoformat()

    with get_db(db_path) as conn:
        rows = conn.execute(
            """SELECT * FROM tenancies
               WHERE status = 'active'
                 AND end_date <= ?
                 AND end_date >= ?
               ORDER BY end_date ASC""",
            (cutoff, today),
        ).fetchall()

    results = []
    for row in rows:
        d = dict(row)
        end = date.fromisoformat(d["end_date"])
        d["days_remaining"] = (end - date.today()).days
        results.append(d)
    return results


def create_renewal_alerts(
    db_path: str | Path,
    tenancy_id: int,
) -> list[int]:
    """Create renewal alert rows at 90, 60, and 30 days before expiry.

    Skips alert dates that are already in the past or already exist.
    Returns the list of newly created alert IDs.
    """
    with get_db(db_path) as conn:
        row = conn.execute(
            "SELECT end_date FROM tenancies WHERE id = ?", (tenancy_id,)
        ).fetchone()
        if not row:
            return []

        end = date.fromisoformat(row["end_date"])
        today = date.today()
        new_ids: list[int] = []

        for days_before in (90, 60, 30):
            alert_date = end - timedelta(days=days_before)
            if alert_date < today:
                continue

            existing = conn.execute(
                """SELECT id FROM renewal_alerts
                   WHERE tenancy_id = ? AND alert_date = ?""",
                (tenancy_id, alert_date.isoformat()),
            ).fetchone()
            if existing:
                continue

            cursor = conn.execute(
                """INSERT INTO renewal_alerts (tenancy_id, alert_date, alert_type)
                   VALUES (?, ?, ?)""",
                (tenancy_id, alert_date.isoformat(), f"{days_before}_day_reminder"),
            )
            new_ids.append(cursor.lastrowid)  # type: ignore[arg-type]

        return new_ids


def get_overdue_cr109(db_path: str | Path) -> list[dict]:
    """Return tenancies where the CR109 was not filed within 1 month of start.

    According to the Rating Ordinance, the landlord must submit Form CR109
    within one month after the tenancy commences.
    """
    one_month_ago = (date.today() - timedelta(days=30)).isoformat()

    with get_db(db_path) as conn:
        rows = conn.execute(
            """SELECT * FROM tenancies
               WHERE cr109_filed = 0
                 AND start_date <= ?
                 AND status = 'active'
               ORDER BY start_date ASC""",
            (one_month_ago,),
        ).fetchall()

    results = []
    for row in rows:
        d = dict(row)
        start = date.fromisoformat(d["start_date"])
        d["days_overdue"] = (date.today() - start).days - 30
        results.append(d)
    return results
