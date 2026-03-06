"""Multi-step confirmation flow using APScheduler.

Schedules confirmation messages at booking time, T-24hr, and T-2hr.
Auto-releases unconfirmed bookings at T-1hr.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from openclaw_shared.database import get_db
from openclaw_shared.mona_events import emit_event

if TYPE_CHECKING:
    from apscheduler.schedulers.asyncio import AsyncIOScheduler

    from fnb_hospitality.no_show_shield.confirmation.messenger import Messenger

logger = logging.getLogger("openclaw.fnb.no-show-shield.sequencer")

STEP_OFFSETS: dict[int, timedelta] = {
    1: timedelta(seconds=0),
    2: timedelta(hours=-24),
    3: timedelta(hours=-2),
}

AUTO_RELEASE_OFFSET = timedelta(hours=-1)


def _job_id(booking_id: int, step: int) -> str:
    return f"nss_confirm_{booking_id}_step{step}"


def _release_job_id(booking_id: int) -> str:
    return f"nss_release_{booking_id}"


def schedule_confirmation_sequence(
    scheduler: AsyncIOScheduler,
    booking_id: int,
    guest_phone: str,
    booking_datetime: datetime,
    db_path: str,
    messenger: Messenger,
) -> list[str]:
    """Schedule the 3-step confirmation sequence and auto-release job.

    Returns list of scheduled job IDs.
    """
    job_ids: list[str] = []
    now = datetime.now()

    for step, offset in STEP_OFFSETS.items():
        run_at = booking_datetime + offset if step > 1 else now
        if run_at <= now:
            if step == 1:
                run_at = now + timedelta(seconds=5)
            else:
                continue

        jid = _job_id(booking_id, step)
        scheduler.add_job(
            process_confirmation_step,
            "date",
            run_date=run_at,
            id=jid,
            replace_existing=True,
            args=[step, booking_id, guest_phone, db_path, messenger],
        )
        job_ids.append(jid)
        logger.info(
            "Scheduled step %d for booking %d at %s", step, booking_id, run_at.isoformat()
        )

    release_at = booking_datetime + AUTO_RELEASE_OFFSET
    if release_at > now:
        rid = _release_job_id(booking_id)
        scheduler.add_job(
            check_and_release_unconfirmed,
            "date",
            run_date=release_at,
            id=rid,
            replace_existing=True,
            args=[db_path, booking_id],
        )
        job_ids.append(rid)
        logger.info("Scheduled auto-release for booking %d at %s", booking_id, release_at.isoformat())

    with get_db(db_path) as conn:
        for step in STEP_OFFSETS:
            conn.execute(
                """INSERT INTO confirmations (booking_id, guest_phone, step, status)
                   VALUES (?, ?, ?, 'scheduled')""",
                (booking_id, guest_phone, step),
            )

    return job_ids


def cancel_confirmation_sequence(
    scheduler: AsyncIOScheduler,
    booking_id: int,
) -> int:
    """Cancel all pending confirmation jobs for a booking. Returns removed count."""
    removed = 0
    for step in STEP_OFFSETS:
        jid = _job_id(booking_id, step)
        try:
            scheduler.remove_job(jid)
            removed += 1
        except Exception:
            pass

    try:
        scheduler.remove_job(_release_job_id(booking_id))
        removed += 1
    except Exception:
        pass

    logger.info("Cancelled %d jobs for booking %d", removed, booking_id)
    return removed


def process_confirmation_step(
    step: int,
    booking_id: int,
    guest_phone: str,
    db_path: str,
    messenger: Messenger,
) -> bool:
    """Execute a single confirmation step: send message and record result."""
    with get_db(db_path) as conn:
        row = conn.execute(
            """SELECT status FROM confirmations
               WHERE booking_id = ? AND step < ? AND response = 'confirmed'""",
            (booking_id, step),
        ).fetchone()
        if row:
            logger.info(
                "Booking %d already confirmed at earlier step, skipping step %d",
                booking_id, step,
            )
            conn.execute(
                """UPDATE confirmations SET status = 'skipped'
                   WHERE booking_id = ? AND step = ?""",
                (booking_id, step),
            )
            return True

        cancelled = conn.execute(
            """SELECT status FROM confirmations
               WHERE booking_id = ? AND step = 1 AND status = 'cancelled'""",
            (booking_id,),
        ).fetchone()
        if cancelled:
            logger.info("Booking %d was cancelled, skipping step %d", booking_id, step)
            return False

    step_labels = {1: "at_booking", 2: "24h_before", 3: "2h_before"}
    success = messenger.send_confirmation(
        guest_phone, booking_id, step_label=step_labels.get(step, "unknown")
    )

    status = "sent" if success else "failed"
    with get_db(db_path) as conn:
        conn.execute(
            """UPDATE confirmations
               SET status = ?, sent_at = CURRENT_TIMESTAMP, channel = ?
               WHERE booking_id = ? AND step = ?""",
            (status, messenger.default_channel, booking_id, step),
        )

    if success:
        emit_event(
            db_path,
            event_type="action_completed",
            tool_name="no-show-shield",
            summary=f"Confirmation step {step} sent for booking #{booking_id}",
        )
    else:
        emit_event(
            db_path,
            event_type="error",
            tool_name="no-show-shield",
            summary=f"Failed to send confirmation step {step} for booking #{booking_id}",
            requires_human_action=True,
        )

    return success


def check_and_release_unconfirmed(db_path: str, booking_id: int) -> list[int]:
    """Check if booking is unconfirmed at T-1hr and release the table.

    Returns list of released booking IDs (typically 0 or 1).
    """
    released: list[int] = []

    with get_db(db_path) as conn:
        confirmed = conn.execute(
            """SELECT id FROM confirmations
               WHERE booking_id = ? AND response = 'confirmed'""",
            (booking_id,),
        ).fetchone()

        if confirmed:
            logger.info("Booking %d is confirmed, no release needed", booking_id)
            return released

        conn.execute(
            """UPDATE confirmations SET status = 'auto_released'
               WHERE booking_id = ? AND status IN ('scheduled', 'sent')""",
            (booking_id,),
        )
        released.append(booking_id)

        logger.warning("Auto-released unconfirmed booking %d", booking_id)
        emit_event(
            db_path,
            event_type="alert",
            tool_name="no-show-shield",
            summary=f"Booking #{booking_id} auto-released (unconfirmed at T-1hr)",
            requires_human_action=True,
        )

    return released
