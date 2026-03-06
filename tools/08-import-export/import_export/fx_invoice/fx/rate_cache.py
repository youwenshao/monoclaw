"""SQLite-backed FX rate caching."""

from __future__ import annotations

from datetime import datetime, timedelta

from openclaw_shared.database import get_db


class RateCache:

    def __init__(self, db_path: str) -> None:
        self.db_path = db_path

    def get_latest_rate(self, base: str, target: str) -> dict | None:
        """Get the most recently cached rate for a currency pair."""
        with get_db(self.db_path) as conn:
            row = conn.execute(
                """SELECT * FROM fx_rates
                   WHERE base_currency = ? AND target_currency = ?
                   ORDER BY fetched_at DESC LIMIT 1""",
                (base, target),
            ).fetchone()
        return dict(row) if row else None

    def is_stale(self, rate_record: dict, max_age_hours: int = 1) -> bool:
        """Check whether a cached rate is older than max_age_hours."""
        fetched_at_str = rate_record.get("fetched_at", "")
        if not fetched_at_str:
            return True
        try:
            fetched_at = datetime.fromisoformat(fetched_at_str)
        except ValueError:
            fetched_at = datetime.strptime(fetched_at_str, "%Y-%m-%d %H:%M:%S")
        return datetime.now() - fetched_at > timedelta(hours=max_age_hours)

    def cache_rates(self, rates: dict, source: str) -> None:
        """Bulk-insert fetched rates into the fx_rates table."""
        base = rates.get("base", "HKD")
        rate_map = rates.get("rates", {})
        with get_db(self.db_path) as conn:
            for target, rate in rate_map.items():
                conn.execute(
                    """INSERT INTO fx_rates (base_currency, target_currency, rate, source)
                       VALUES (?,?,?,?)""",
                    (base, target, rate, source),
                )

    def get_rate_history(
        self, base: str, target: str, days: int = 30
    ) -> list[dict]:
        """Return cached rates for a pair over the last N days."""
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        with get_db(self.db_path) as conn:
            rows = conn.execute(
                """SELECT * FROM fx_rates
                   WHERE base_currency = ? AND target_currency = ?
                     AND fetched_at >= ?
                   ORDER BY fetched_at""",
                (base, target, cutoff),
            ).fetchall()
        return [dict(r) for r in rows]
