"""Telegram Bot handler for the IntakeBot."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from openclaw_shared.database import get_db

from legal.intake_bot.conversation_flow import IntakeConversation, State

logger = logging.getLogger("openclaw.legal.intake_bot.telegram")

_conversations: dict[str, IntakeConversation] = {}


def handle_telegram_update(
    update: dict[str, Any],
    db_path: str | Path,
    llm: Any = None,
) -> dict[str, Any]:
    """Process a Telegram webhook update.

    Extracts chat_id and message text, looks up or creates conversation state,
    passes through IntakeConversation, saves to DB, and returns a response dict.
    """
    parsed = _parse_telegram_update(update)
    chat_id = parsed["chat_id"]
    text = parsed["text"]

    if not chat_id or not text:
        return {"chat_id": chat_id, "text": "Sorry, I couldn't process your message."}

    user_display = parsed["from_user"].get("first_name", "")
    if parsed["from_user"].get("last_name"):
        user_display += f" {parsed['from_user']['last_name']}"
    user_display = user_display.strip() or "Telegram User"

    client_id = _lookup_or_create_client(chat_id, user_display, db_path)

    _save_message(client_id, "telegram", "inbound", text, db_path, state=None)

    conv = _conversations.get(chat_id)
    if conv is None:
        conv = _load_conversation_state(chat_id, db_path)
        _conversations[chat_id] = conv

    response_text = conv.process_message(text)
    current_state = conv.get_state()

    _save_message(client_id, "telegram", "outbound", response_text, db_path, state=current_state)

    if current_state == State.COMPLETE.value:
        _finalize_intake(client_id, conv.get_collected_data(), db_path)
        _conversations.pop(chat_id, None)
    elif current_state == State.HUMAN_ESCALATION.value:
        _conversations.pop(chat_id, None)

    return {"chat_id": chat_id, "text": response_text}


def _parse_telegram_update(data: dict[str, Any]) -> dict[str, Any]:
    message = data.get("message") or data.get("edited_message") or {}
    chat = message.get("chat", {})
    from_user = message.get("from", {})

    return {
        "chat_id": str(chat.get("id", "")),
        "text": message.get("text", "").strip(),
        "from_user": {
            "id": from_user.get("id"),
            "first_name": from_user.get("first_name", ""),
            "last_name": from_user.get("last_name", ""),
            "username": from_user.get("username", ""),
            "language_code": from_user.get("language_code", "en"),
        },
        "message_id": message.get("message_id"),
        "update_id": data.get("update_id"),
    }


def _lookup_or_create_client(
    chat_id: str,
    display_name: str,
    db_path: str | Path,
) -> int:
    with get_db(db_path) as conn:
        row = conn.execute(
            "SELECT id FROM clients WHERE wechat_id = ? OR phone = ?",
            (f"tg:{chat_id}", f"tg:{chat_id}"),
        ).fetchone()

        if row:
            return row[0]

        conn.execute(
            """INSERT INTO clients (name_en, wechat_id, source_channel, status)
               VALUES (?, ?, 'telegram', 'pending_review')""",
            (display_name, f"tg:{chat_id}"),
        )
        new_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    logger.info("Created new client id=%d for Telegram chat %s", new_id, chat_id)
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


def _load_conversation_state(chat_id: str, db_path: str | Path) -> IntakeConversation:
    """Reconstruct conversation from the last outbound message's state."""
    with get_db(db_path) as conn:
        row = conn.execute(
            """SELECT c.state FROM conversations c
               JOIN clients cl ON cl.id = c.client_id
               WHERE cl.wechat_id = ?
                 AND c.direction = 'outbound'
                 AND c.state IS NOT NULL
               ORDER BY c.created_at DESC LIMIT 1""",
            (f"tg:{chat_id}",),
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

    logger.info("Finalized intake for client %d via Telegram", client_id)


async def send_telegram_message(
    chat_id: str,
    text: str,
    config: dict[str, Any],
) -> bool:
    """Send a text message via the Telegram Bot API. Returns True on success."""
    bot_token = config.get("telegram_bot_token", "")
    if not bot_token:
        logger.warning("Telegram bot not configured — skipping send to chat %s", chat_id)
        return False

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"

    try:
        import httpx

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                url,
                json={
                    "chat_id": chat_id,
                    "text": text[:4096],
                    "parse_mode": "HTML",
                },
            )

            if resp.status_code == 200 and resp.json().get("ok"):
                logger.info("Telegram message sent to chat %s", chat_id)
                return True

            logger.error("Telegram API error %d: %s", resp.status_code, resp.text[:300])
            return False

    except ImportError:
        logger.error("httpx not installed — cannot send Telegram messages")
        return False
    except Exception:
        logger.exception("Failed to send Telegram message to chat %s", chat_id)
        return False
