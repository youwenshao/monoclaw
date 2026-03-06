"""Auto-fill cancelled/no-show slots from the waitlist."""

from __future__ import annotations

import logging
from typing import Any

from openclaw_shared.database import get_db
from openclaw_shared.mona_events import emit_event

from fnb_hospitality.no_show_shield.confirmation.messenger import Messenger
from fnb_hospitality.no_show_shield.waitlist.manager import (
    find_matching_entries,
    update_waitlist_status,
)

logger = logging.getLogger("openclaw.fnb.no-show-shield.auto-fill")


def attempt_auto_fill(
    db_path: str,
    available_date: str,
    available_time: str,
    available_party_size: int,
    released_booking_id: int | None = None,
    messenger: Messenger | None = None,
) -> dict[str, Any] | None:
    """Find the best waitlist match and send an offer.

    Returns the matched waitlist entry dict if found, or None.
    """
    candidates = find_matching_entries(
        db_path, available_date, available_time, available_party_size
    )

    if not candidates:
        logger.info(
            "No waitlist match for %s %s (%d pax)",
            available_date, available_time, available_party_size,
        )
        return None

    best = candidates[0]
    update_waitlist_status(db_path, best["id"], "offered", released_booking_id)

    if messenger:
        messenger.send_waitlist_offer(
            phone=best["guest_phone"],
            date=available_date,
            time=available_time,
            party_size=best["party_size"],
        )

    emit_event(
        db_path,
        event_type="action_completed",
        tool_name="no-show-shield",
        summary=(
            f"Waitlist offer sent to {best.get('guest_name', best['guest_phone'])} "
            f"for {available_date} {available_time} ({best['party_size']} pax)"
        ),
    )

    logger.info("Auto-fill offer sent to waitlist entry #%d", best["id"])
    return best


def process_offer_response(
    db_path: str,
    waitlist_entry_id: int,
    accepted: bool,
    messenger: Messenger | None = None,
) -> dict[str, Any]:
    """Handle a guest's response to a waitlist offer.

    If accepted, marks entry as 'accepted'. If declined, offers to next candidate.
    """
    with get_db(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM waitlist WHERE id = ?", (waitlist_entry_id,)
        ).fetchone()

    if not row:
        return {"error": "Waitlist entry not found"}

    entry = dict(row)

    if accepted:
        update_waitlist_status(db_path, waitlist_entry_id, "accepted")
        emit_event(
            db_path,
            event_type="action_completed",
            tool_name="no-show-shield",
            summary=f"Waitlist entry #{waitlist_entry_id} accepted table offer",
        )
        return {"status": "accepted", "entry": entry}

    update_waitlist_status(db_path, waitlist_entry_id, "declined")

    next_match = attempt_auto_fill(
        db_path,
        available_date=entry["preferred_date"],
        available_time=entry["preferred_time"],
        available_party_size=entry["party_size"],
        released_booking_id=entry.get("offered_booking_id"),
        messenger=messenger,
    )

    return {
        "status": "declined",
        "entry": entry,
        "next_offer": next_match,
    }


def on_cancellation(
    db_path: str,
    booking_date: str,
    booking_time: str,
    party_size: int,
    booking_id: int,
    messenger: Messenger | None = None,
) -> dict[str, Any] | None:
    """Triggered when a booking is cancelled or a no-show is detected.

    Attempts to fill the slot from the waitlist.
    """
    logger.info(
        "Slot freed: %s %s (%d pax) from booking #%d",
        booking_date, booking_time, party_size, booking_id,
    )
    return attempt_auto_fill(
        db_path,
        available_date=booking_date,
        available_time=booking_time,
        available_party_size=party_size,
        released_booking_id=booking_id,
        messenger=messenger,
    )
