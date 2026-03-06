"""Twilio WhatsApp webhook handler for the IntakeBot."""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any

from openclaw_shared.database import get_db

from legal.intake_bot.conversation_flow import IntakeConversation, State

logger = logging.getLogger("openclaw.legal.intake_bot.whatsapp")

_conversations: dict[str, IntakeConversation] = {}
_last_send_ts: float = 0.0


def handle_whatsapp_message(
    form_data: dict[str, Any],
    db_path: str | Path,
    llm: Any = None,
) -> str:
    """Process an incoming Twilio WhatsApp webhook.

    Extracts sender phone and message body, looks up or creates conversation
    state, passes through IntakeConversation, saves to DB, and returns a
    TwiML XML response string.
    """
    parsed = _parse_twilio_webhook(form_data)
    sender = parsed["from_number"]
    body = parsed["body"]

    if not sender or not body:
        return _twiml_response("Sorry, I couldn't process your message. Please try again.")

    client_id = _lookup_or_create_client(sender, parsed.get("profile_name", ""), db_path)

    _save_message(client_id, "whatsapp", "inbound", body, db_path, state=None)

    conv = _conversations.get(sender)
    if conv is None:
        conv = _load_conversation_state(sender, db_path)
        _conversations[sender] = conv

    response_text = conv.process_message(body)
    current_state = conv.get_state()

    _save_message(client_id, "whatsapp", "outbound", response_text, db_path, state=current_state)

    if current_state == State.COMPLETE.value:
        _finalize_intake(client_id, conv.get_collected_data(), db_path)
        _conversations.pop(sender, None)
    elif current_state == State.HUMAN_ESCALATION.value:
        _conversations.pop(sender, None)

    return _twiml_response(response_text)


def _parse_twilio_webhook(form_data: dict[str, Any]) -> dict[str, Any]:
    from_number = str(form_data.get("From", ""))
    body = str(form_data.get("Body", "")).strip()

    media_urls: list[str] = []
    num_media = int(form_data.get("NumMedia", 0))
    for i in range(num_media):
        url = form_data.get(f"MediaUrl{i}")
        if url:
            media_urls.append(str(url))

    return {
        "from_number": from_number,
        "body": body,
        "media_urls": media_urls,
        "profile_name": str(form_data.get("ProfileName", "")),
        "message_sid": str(form_data.get("MessageSid", "")),
    }


def _twiml_response(text: str) -> str:
    escaped = (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        "<Response>"
        f"<Message>{escaped}</Message>"
        "</Response>"
    )


def _lookup_or_create_client(
    phone: str,
    profile_name: str,
    db_path: str | Path,
) -> int:
    normalized = phone.replace("whatsapp:", "").strip()

    with get_db(db_path) as conn:
        row = conn.execute(
            "SELECT id FROM clients WHERE phone = ? OR whatsapp_number = ?",
            (normalized, normalized),
        ).fetchone()

        if row:
            return row[0]

        conn.execute(
            """INSERT INTO clients (name_en, phone, whatsapp_number, source_channel, status)
               VALUES (?, ?, ?, 'whatsapp', 'pending_review')""",
            (profile_name or "WhatsApp User", normalized, normalized),
        )
        new_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    logger.info("Created new client id=%d for WhatsApp %s", new_id, normalized)
    return new_id


def _save_message(
    client_id: int,
    channel: str,
    direction: str,
    text: str,
    db_path: str | Path,
    state: str | None,
) -> None:
    with get_db(db_path) as conn:
        conn.execute(
            """INSERT INTO conversations (client_id, channel, direction, message_text, state)
               VALUES (?, ?, ?, ?, ?)""",
            (client_id, channel, direction, text, state),
        )


def _load_conversation_state(phone: str, db_path: str | Path) -> IntakeConversation:
    """Reconstruct conversation state from the last outbound message's state field."""
    normalized = phone.replace("whatsapp:", "").strip()

    with get_db(db_path) as conn:
        row = conn.execute(
            """SELECT c.state FROM conversations c
               JOIN clients cl ON cl.id = c.client_id
               WHERE (cl.phone = ? OR cl.whatsapp_number = ?)
                 AND c.direction = 'outbound'
                 AND c.state IS NOT NULL
               ORDER BY c.created_at DESC LIMIT 1""",
            (normalized, normalized),
        ).fetchone()

    conv = IntakeConversation()
    if row and row[0]:
        try:
            conv._state = State(row[0])
        except ValueError:
            pass

    return conv


def _finalize_intake(
    client_id: int,
    data: dict[str, Any],
    db_path: str | Path,
) -> None:
    """Create a matter record from completed conversation data."""
    with get_db(db_path) as conn:
        if data.get("name_en"):
            conn.execute(
                "UPDATE clients SET name_en = ?, name_tc = ? WHERE id = ?",
                (data.get("name_en"), data.get("name_tc", ""), client_id),
            )
        if data.get("email"):
            conn.execute(
                "UPDATE clients SET email = ? WHERE id = ?",
                (data["email"], client_id),
            )

        conn.execute(
            """INSERT INTO matters
               (client_id, matter_type, description, adverse_party_name,
                adverse_party_name_tc, urgency, status)
               VALUES (?, ?, ?, ?, ?, ?, 'intake')""",
            (
                client_id,
                data.get("matter_type", "other"),
                data.get("matter_description", ""),
                data.get("adverse_party_name"),
                data.get("adverse_party_name_tc"),
                data.get("urgency", "normal"),
            ),
        )

    logger.info("Finalized intake for client %d via WhatsApp", client_id)


async def send_whatsapp_message(to: str, text: str, config: dict[str, Any]) -> bool:
    """Send a WhatsApp message via Twilio. Returns True on success."""
    global _last_send_ts

    account_sid = config.get("twilio_account_sid", "")
    auth_token = config.get("twilio_auth_token", "")
    from_number = config.get("twilio_whatsapp_from", "")

    if not all([account_sid, auth_token, from_number]):
        logger.warning("WhatsApp not configured — skipping send to %s", to)
        return False

    elapsed = time.monotonic() - _last_send_ts
    if elapsed < 1.0:
        import asyncio
        await asyncio.sleep(1.0 - elapsed)

    try:
        import httpx

        whatsapp_to = to if to.startswith("whatsapp:") else f"whatsapp:{to}"
        whatsapp_from = from_number if from_number.startswith("whatsapp:") else f"whatsapp:{from_number}"

        url = f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json"

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                url,
                auth=(account_sid, auth_token),
                data={
                    "From": whatsapp_from,
                    "To": whatsapp_to,
                    "Body": text[:1600],
                },
            )
            _last_send_ts = time.monotonic()

            if resp.status_code in (200, 201):
                logger.info("WhatsApp sent to %s (sid=%s)", to, resp.json().get("sid"))
                return True

            logger.error("Twilio error %d: %s", resp.status_code, resp.text[:300])
            return False

    except ImportError:
        logger.error("httpx not installed — cannot send WhatsApp messages")
        return False
    except Exception:
        logger.exception("Failed to send WhatsApp to %s", to)
        return False
