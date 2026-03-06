"""Instagram Graph API webhook handler for DM-based booking messages."""

from __future__ import annotations

import logging
from typing import Any

from openclaw_shared.database import get_db
from openclaw_shared.mona_events import emit_event

logger = logging.getLogger("openclaw.table_master.channels.instagram")

VERIFY_TOKEN = "tablemaster_ig_verify"


def verify_webhook(mode: str, token: str, challenge: str) -> str | None:
    """Handle the Instagram webhook verification handshake.

    Returns the ``hub.challenge`` value if verification succeeds, else ``None``.
    """
    if mode == "subscribe" and token == VERIFY_TOKEN:
        return challenge
    return None


async def handle_webhook(
    payload: dict[str, Any],
    *,
    llm: Any,
    db_path: str,
    mona_db_path: str,
    parse_fn: Any,
    config: Any,
) -> list[dict[str, Any]]:
    """Process Instagram webhook payload and return a list of created bookings.

    The Instagram webhook sends batches of messaging events via the Graph API.
    Each entry may contain multiple ``messaging`` events.
    """
    results: list[dict[str, Any]] = []

    entries = payload.get("entry", [])
    for entry in entries:
        messaging_events = entry.get("messaging", [])
        for event in messaging_events:
            message = event.get("message", {})
            text = message.get("text", "").strip()
            sender_id = event.get("sender", {}).get("id", "unknown")

            if not text:
                continue

            parsed = await parse_fn(llm, text)
            language = parsed.get("language", "en")

            if parsed.get("party_size") and parsed.get("booking_date"):
                booking = _create_ig_booking(
                    parsed,
                    sender_id=sender_id,
                    db_path=db_path,
                    mona_db_path=mona_db_path,
                )
                results.append(booking)
            else:
                logger.info("IG message from %s lacked booking details: %s", sender_id, text[:80])

    return results


def _create_ig_booking(
    parsed: dict[str, Any],
    *,
    sender_id: str,
    db_path: str,
    mona_db_path: str,
) -> dict[str, Any]:
    guest_name = parsed.get("guest_name") or f"IG:{sender_id[:8]}"
    party_size = parsed["party_size"]
    booking_date = parsed["booking_date"]
    booking_time = parsed.get("booking_time", "19:00")
    special = parsed.get("special_requests", "")
    language = parsed.get("language", "en")

    with get_db(db_path) as conn:
        cursor = conn.execute(
            """INSERT INTO bookings
               (guest_name, guest_phone, party_size, booking_date, booking_time,
                channel, channel_ref, status, special_requests, language_pref)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (guest_name, "", party_size, booking_date, booking_time,
             "instagram", sender_id, "pending", special, language),
        )
        booking_id = cursor.lastrowid

    emit_event(
        mona_db_path,
        event_type="action_completed",
        tool_name="table-master",
        summary=f"Instagram booking #{booking_id} from {guest_name} ({party_size}pax)",
    )

    return {
        "id": booking_id,
        "guest_name": guest_name,
        "party_size": party_size,
        "booking_date": booking_date,
        "booking_time": booking_time,
        "channel": "instagram",
        "status": "pending",
    }


async def send_ig_reply(
    recipient_id: str,
    text: str,
    *,
    access_token: str,
) -> bool:
    """Send a reply to an Instagram user via the Graph API.

    Returns ``True`` on success.  Falls back to logging on failure so that
    the caller never crashes on a messaging glitch.
    """
    import httpx

    url = f"https://graph.facebook.com/v18.0/me/messages"
    payload = {
        "recipient": {"id": recipient_id},
        "message": {"text": text},
    }
    headers = {"Authorization": f"Bearer {access_token}"}

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            return True
    except Exception as exc:
        logger.error("Failed to send IG reply to %s: %s", recipient_id, exc)
        return False
