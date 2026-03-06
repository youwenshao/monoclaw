"""Auto-confirmation logic — confirm bookings within 60 seconds, send
bilingual WhatsApp messages, and enforce a 2-hour confirmation window."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

from openclaw_shared.database import get_db
from openclaw_shared.mona_events import emit_event

from fnb_hospitality.table_master.channels.whatsapp import (
    build_confirmation_message,
    build_cancellation_message,
)

logger = logging.getLogger("openclaw.table_master.booking.confirmer")

AUTO_CONFIRM_SECONDS = 60
CONFIRMATION_WINDOW_HOURS = 2


async def auto_confirm_booking(
    db_path: str,
    booking_id: int,
    *,
    mona_db_path: str,
    send_whatsapp: bool = True,
    twilio_client: Any | None = None,
    twilio_from: str = "",
) -> dict[str, Any]:
    """Attempt to auto-confirm a booking that has a table assigned.

    A booking is auto-confirmed when:
    1. It has ``status='pending'`` and a ``table_id`` assigned.
    2. It was created fewer than ``AUTO_CONFIRM_SECONDS`` ago (or we're
       called explicitly from the assign flow).

    Returns the updated booking dict.
    """
    with get_db(db_path) as conn:
        row = conn.execute("SELECT * FROM bookings WHERE id = ?", (booking_id,)).fetchone()
        if not row:
            return {"error": "Booking not found"}

        booking = dict(row)

        if booking["status"] != "pending":
            return {"error": f"Booking is already {booking['status']}"}
        if not booking.get("table_id"):
            return {"error": "No table assigned — cannot confirm"}

        now = datetime.utcnow()
        conn.execute(
            "UPDATE bookings SET status = 'confirmed', confirmed_at = ? WHERE id = ?",
            (now.isoformat(), booking_id),
        )
        booking["status"] = "confirmed"
        booking["confirmed_at"] = now.isoformat()

        table_row = conn.execute(
            "SELECT table_number FROM tables WHERE id = ?", (booking["table_id"],)
        ).fetchone()
        booking["table_number"] = table_row["table_number"] if table_row else ""

    emit_event(
        mona_db_path,
        event_type="action_completed",
        tool_name="table-master",
        summary=f"Booking #{booking_id} auto-confirmed (Table {booking['table_number']})",
    )

    if send_whatsapp and twilio_client and booking.get("guest_phone"):
        language = booking.get("language_pref", "zh")
        msg = build_confirmation_message(booking, language)
        _send_whatsapp(twilio_client, twilio_from, booking["guest_phone"], msg)

    return booking


async def expire_unconfirmed_bookings(
    db_path: str,
    *,
    mona_db_path: str,
    twilio_client: Any | None = None,
    twilio_from: str = "",
) -> list[int]:
    """Cancel bookings that have been pending longer than the confirmation window.

    Returns a list of cancelled booking IDs.
    """
    cutoff = (datetime.utcnow() - timedelta(hours=CONFIRMATION_WINDOW_HOURS)).isoformat()
    cancelled_ids: list[int] = []

    with get_db(db_path) as conn:
        rows = conn.execute(
            """SELECT * FROM bookings
               WHERE status = 'pending'
                 AND created_at < ?""",
            (cutoff,),
        ).fetchall()

        for row in rows:
            booking = dict(row)
            conn.execute(
                "UPDATE bookings SET status = 'cancelled' WHERE id = ?",
                (booking["id"],),
            )

            if booking.get("table_id"):
                conn.execute(
                    "UPDATE tables SET status = 'available', current_booking_id = NULL WHERE id = ?",
                    (booking["table_id"],),
                )

            cancelled_ids.append(booking["id"])

            if twilio_client and booking.get("guest_phone"):
                language = booking.get("language_pref", "zh")
                msg = build_cancellation_message(booking, language)
                _send_whatsapp(twilio_client, twilio_from, booking["guest_phone"], msg)

    if cancelled_ids:
        emit_event(
            mona_db_path,
            event_type="alert",
            tool_name="table-master",
            summary=f"Expired {len(cancelled_ids)} unconfirmed booking(s): {cancelled_ids}",
        )

    return cancelled_ids


async def confirm_booking_manual(
    db_path: str,
    booking_id: int,
    *,
    mona_db_path: str,
    twilio_client: Any | None = None,
    twilio_from: str = "",
) -> dict[str, Any]:
    """Manually confirm a booking (e.g. from the dashboard)."""
    with get_db(db_path) as conn:
        row = conn.execute("SELECT * FROM bookings WHERE id = ?", (booking_id,)).fetchone()
        if not row:
            return {"error": "Booking not found"}

        booking = dict(row)
        if booking["status"] == "confirmed":
            return {"error": "Already confirmed"}
        if booking["status"] == "cancelled":
            return {"error": "Cannot confirm a cancelled booking"}

        now = datetime.utcnow()
        conn.execute(
            "UPDATE bookings SET status = 'confirmed', confirmed_at = ? WHERE id = ?",
            (now.isoformat(), booking_id),
        )
        booking["status"] = "confirmed"
        booking["confirmed_at"] = now.isoformat()

        table_row = None
        if booking.get("table_id"):
            table_row = conn.execute(
                "SELECT table_number FROM tables WHERE id = ?", (booking["table_id"],)
            ).fetchone()
        booking["table_number"] = table_row["table_number"] if table_row else ""

    emit_event(
        mona_db_path,
        event_type="action_completed",
        tool_name="table-master",
        summary=f"Booking #{booking_id} manually confirmed",
    )

    if twilio_client and booking.get("guest_phone"):
        language = booking.get("language_pref", "zh")
        msg = build_confirmation_message(booking, language)
        _send_whatsapp(twilio_client, twilio_from, booking["guest_phone"], msg)

    return booking


def _send_whatsapp(client: Any, from_number: str, to_number: str, body: str) -> None:
    """Best-effort WhatsApp send via Twilio."""
    try:
        client.messages.create(
            from_=f"whatsapp:{from_number}",
            to=f"whatsapp:{to_number}",
            body=body,
        )
    except Exception as exc:
        logger.error("Failed to send WhatsApp to %s: %s", to_number, exc)
