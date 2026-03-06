"""Automatic supplier ping scheduling and delivery."""

from __future__ import annotations

import logging
from datetime import date, datetime, time, timezone, timedelta
from pathlib import Path
from typing import Any

from openclaw_shared.database import get_db

logger = logging.getLogger("openclaw.supplier-bot.auto-ping")

CST = timezone(timedelta(hours=8))

FACTORY_OPEN = time(8, 0)
FACTORY_CLOSE = time(17, 30)


class AutoPing:
    """Schedule and deliver follow-up pings to suppliers during factory hours."""

    def __init__(self, db_path: str | Path, config: dict[str, Any] | None = None) -> None:
        self.db_path = db_path
        self.config = config or {}
        self.factory_open: time = self.config.get("factory_open", FACTORY_OPEN)
        self.factory_close: time = self.config.get("factory_close", FACTORY_CLOSE)
        self.holidays: list[str] = self.config.get("holidays", [])

    def schedule_ping(
        self,
        supplier_id: int,
        order_id: int | None,
        ping_type: str,
        scheduled_time: str | datetime,
    ) -> int:
        """Insert a new ping and return its ID."""
        if isinstance(scheduled_time, datetime):
            scheduled_time = scheduled_time.isoformat()

        with get_db(self.db_path) as conn:
            cursor = conn.execute(
                """INSERT INTO status_pings
                   (supplier_id, order_id, ping_type, scheduled_time)
                   VALUES (?,?,?,?)""",
                (supplier_id, order_id, ping_type, scheduled_time),
            )
            ping_id = cursor.lastrowid

        logger.info("Ping #%d scheduled for supplier=%d type=%s at %s", ping_id, supplier_id, ping_type, scheduled_time)
        return ping_id  # type: ignore[return-value]

    def get_due_pings(self) -> list[dict[str, Any]]:
        """Return pings whose scheduled_time <= now and have not been sent."""
        now = datetime.now().isoformat()
        with get_db(self.db_path) as conn:
            rows = conn.execute(
                """SELECT p.*, s.company_name_cn, s.wechat_id
                   FROM status_pings p
                   LEFT JOIN suppliers s ON p.supplier_id = s.id
                   WHERE p.sent_time IS NULL AND p.scheduled_time <= ?
                   ORDER BY p.scheduled_time ASC""",
                (now,),
            ).fetchall()
        return [dict(r) for r in rows]

    def mark_sent(self, ping_id: int) -> None:
        """Record that a ping has been sent."""
        now = datetime.now().isoformat()
        with get_db(self.db_path) as conn:
            conn.execute(
                "UPDATE status_pings SET sent_time = ? WHERE id = ?",
                (now, ping_id),
            )
        logger.info("Ping #%d marked as sent", ping_id)

    def is_factory_hours(self) -> bool:
        """Check whether the current time is within Mainland China factory hours."""
        now_cst = datetime.now(CST).time()
        return self.factory_open <= now_cst <= self.factory_close

    def is_holiday(self, check_date: date | str) -> bool:
        """Check if the given date is a configured mainland holiday."""
        if isinstance(check_date, str):
            check_date = date.fromisoformat(check_date)
        iso = check_date.isoformat()
        if iso in self.holidays:
            return True
        if check_date.weekday() >= 5:  # Saturday / Sunday
            return True
        return False

    def send_follow_up(self, ping_id: int) -> dict[str, Any]:
        """Increment follow_up_count and return the updated ping."""
        with get_db(self.db_path) as conn:
            conn.execute(
                "UPDATE status_pings SET follow_up_count = follow_up_count + 1 WHERE id = ?",
                (ping_id,),
            )
            row = conn.execute("SELECT * FROM status_pings WHERE id = ?", (ping_id,)).fetchone()

        if row:
            logger.info("Ping #%d follow-up count → %d", ping_id, row["follow_up_count"])
            return dict(row)
        return {"ping_id": ping_id, "error": "not_found"}
