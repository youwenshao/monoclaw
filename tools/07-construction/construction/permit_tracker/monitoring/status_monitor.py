"""Periodic submission status checker with APScheduler integration."""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from openclaw_shared.database import get_db

logger = logging.getLogger("openclaw.construction.permit_tracker.monitoring.status_monitor")

HKT = ZoneInfo("Asia/Hong_Kong")
BUSINESS_HOURS = (9, 18)


class StatusMonitor:
    """Manages scheduled status checks for BD submissions.

    Runs checks during business hours (Mon-Fri 09:00-18:00 HKT) with
    higher frequency, and once daily on weekends.
    """

    def __init__(self, db_path: Any, app_state: Any) -> None:
        self.db_path = db_path
        self.app_state = app_state
        self._scheduler: Any = None

    def start(self) -> None:
        """Start the APScheduler background job."""
        try:
            from apscheduler.schedulers.asyncio import AsyncIOScheduler
            from apscheduler.triggers.cron import CronTrigger
        except ImportError:
            logger.warning(
                "APScheduler not installed — automatic status monitoring disabled. "
                "Install with: pip install apscheduler"
            )
            return

        self._scheduler = AsyncIOScheduler(timezone=HKT)

        self._scheduler.add_job(
            check_all_submissions,
            CronTrigger(
                day_of_week="mon-fri",
                hour="9,12,15,18",
                timezone=HKT,
            ),
            args=[self.db_path, self.app_state],
            id="weekday_status_check",
            name="Weekday BD status check",
            replace_existing=True,
        )

        self._scheduler.add_job(
            check_all_submissions,
            CronTrigger(
                day_of_week="sat,sun",
                hour="12",
                timezone=HKT,
            ),
            args=[self.db_path, self.app_state],
            id="weekend_status_check",
            name="Weekend BD status check",
            replace_existing=True,
        )

        self._scheduler.start()
        logger.info("StatusMonitor scheduler started")

    def stop(self) -> None:
        if self._scheduler:
            self._scheduler.shutdown(wait=False)
            logger.info("StatusMonitor scheduler stopped")


async def check_all_submissions(db_path: Any, app_state: Any) -> list[dict]:
    """Check status of all active submissions.

    Skips submissions already in terminal states (Approved, Consent Issued,
    Rejected, Withdrawn, Completed).
    """
    now = datetime.now(HKT)
    if not _is_business_hours(now) and now.weekday() < 5:
        logger.debug("Outside business hours, skipping check")
        return []

    terminal_statuses = ("Approved", "Consent Issued", "Rejected", "Withdrawn", "Completed")

    with get_db(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM submissions WHERE current_status NOT IN ({}) OR current_status IS NULL".format(
                ",".join("?" for _ in terminal_statuses)
            ),
            terminal_statuses,
        ).fetchall()

    submissions = [dict(r) for r in rows]
    logger.info("Checking %d active submissions", len(submissions))

    results: list[dict] = []
    for submission in submissions:
        try:
            result = await check_single_submission(submission, app_state)
            results.append(result)
        except Exception:
            logger.exception(
                "Error checking submission %s (id=%s)",
                submission.get("bd_reference"),
                submission.get("id"),
            )

    return results


async def check_single_submission(
    submission: dict,
    app_state: Any,
) -> dict[str, Any]:
    """Check a single submission's status and process any changes.

    Dispatches to the appropriate scraper based on submission_type and
    triggers alert_engine if the status has changed.
    """
    sub_id = submission["id"]
    bd_ref = submission.get("bd_reference", "")
    sub_type = submission.get("submission_type", "GBP")
    old_status = submission.get("current_status", "")
    db_path = app_state.db_paths["permit_tracker"]
    config = app_state.config

    logger.info("Checking submission %s (type=%s, ref=%s)", sub_id, sub_type, bd_ref)

    if sub_type == "minor_works":
        from construction.permit_tracker.scrapers.minor_works import check_minor_works_status
        mw_class = submission.get("minor_works_class", "I") or "I"
        result = await check_minor_works_status(bd_ref, mw_class)
    elif sub_type == "nwsc":
        from construction.permit_tracker.scrapers.nwsc import check_nwsc_status
        result = await check_nwsc_status(bd_ref)
    else:
        from construction.permit_tracker.scrapers.bd_portal import BDPortalScraper
        creds = config.extra.get("permit_tracker", {}).get("bd_portal_credentials", {})
        scraper = BDPortalScraper(creds)
        cache_dir = app_state.workspace / "cache" / "bd_portal"
        scraper.set_cache_dir(cache_dir)
        try:
            result = await scraper.scrape_status(bd_ref)
        finally:
            await scraper.close()

    new_status = result.get("status", "Unknown")
    now_iso = datetime.now(HKT).isoformat()

    with get_db(db_path) as conn:
        conn.execute(
            "UPDATE submissions SET last_checked = ? WHERE id = ?",
            (now_iso, sub_id),
        )

    status_changed = (
        new_status != "Unknown"
        and new_status != old_status
        and old_status is not None
    )

    if status_changed:
        _record_status_change(db_path, sub_id, new_status, now_iso, result)
        await _trigger_alerts(db_path, app_state, submission, old_status, new_status)
    elif _html_content_changed(db_path, sub_id, result):
        logger.info(
            "HTML content changed for %s but status unchanged (%s)",
            bd_ref, new_status,
        )

    return {
        "submission_id": sub_id,
        "bd_reference": bd_ref,
        "old_status": old_status,
        "new_status": new_status,
        "changed": status_changed,
        "checked_at": now_iso,
        **{k: v for k, v in result.items() if k not in ("raw_html",)},
    }


def _record_status_change(
    db_path: Any,
    sub_id: int,
    new_status: str,
    timestamp: str,
    result: dict,
) -> None:
    with get_db(db_path) as conn:
        conn.execute(
            "UPDATE submissions SET current_status = ? WHERE id = ?",
            (new_status, sub_id),
        )
        conn.execute(
            "INSERT INTO status_history (submission_id, status, status_date, details) VALUES (?,?,?,?)",
            (sub_id, new_status, timestamp, result.get("details", "")),
        )
    logger.info("Recorded status change to '%s' for submission %s", new_status, sub_id)


async def _trigger_alerts(
    db_path: Any,
    app_state: Any,
    submission: dict,
    old_status: str,
    new_status: str,
) -> None:
    try:
        from construction.permit_tracker.monitoring.alert_engine import process_status_change
        mona_db = app_state.db_paths["mona_events"]
        await process_status_change(db_path, mona_db, submission, old_status, new_status)
    except Exception:
        logger.exception("Failed to trigger alerts for submission %s", submission.get("id"))


def _html_content_changed(db_path: Any, sub_id: int, result: dict) -> bool:
    """Compare cached HTML hash to detect page changes even without status change."""
    raw_html = result.get("raw_html")
    if not raw_html:
        return False

    new_hash = hashlib.sha256(raw_html.encode("utf-8")).hexdigest()

    with get_db(db_path) as conn:
        row = conn.execute(
            "SELECT details FROM status_history WHERE submission_id = ? "
            "ORDER BY detected_at DESC LIMIT 1",
            (sub_id,),
        ).fetchone()

    if row and row["details"]:
        old_hash = row["details"].split("html_hash:")[-1].strip() if "html_hash:" in (row["details"] or "") else ""
        if old_hash and old_hash != new_hash:
            return True

    return False


def _is_business_hours(now: datetime) -> bool:
    return BUSINESS_HOURS[0] <= now.hour < BUSINESS_HOURS[1]
