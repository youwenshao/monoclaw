"""WhatsApp broadcast messaging via Twilio."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from openclaw_shared.database import get_db


def send_broadcast(
    db_path: str | Path,
    message: str,
    customer_tags: list[str] | None = None,
    twilio_client: Any | None = None,
    twilio_from: str = "",
) -> dict[str, Any]:
    """Send *message* to matching customers and record outbound messages.

    If *customer_tags* is provided, only customers whose ``tags`` field
    contains at least one of the specified tags are targeted.
    Returns a summary dict with ``sent``, ``failed``, and ``recipients``.
    """
    with get_db(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM customers WHERE whatsapp_enabled = 1"
        ).fetchall()

    customers = [dict(r) for r in rows]

    if customer_tags:
        tag_set = {t.lower() for t in customer_tags}
        customers = [
            c for c in customers
            if c.get("tags")
            and tag_set & {t.strip().lower() for t in c["tags"].split(",")}
        ]

    sent = 0
    failed = 0
    recipients: list[str] = []

    for customer in customers:
        phone = customer.get("phone", "")
        if not phone:
            failed += 1
            continue

        if twilio_client and twilio_from:
            try:
                twilio_client.messages.create(
                    body=message,
                    from_=f"whatsapp:{twilio_from}",
                    to=f"whatsapp:+852{phone}" if not phone.startswith("+") else f"whatsapp:{phone}",
                )
            except Exception:
                failed += 1
                continue

        with get_db(db_path) as conn:
            conn.execute(
                """INSERT INTO whatsapp_messages
                   (customer_id, direction, message_text, message_type)
                   VALUES (?, 'outbound', ?, 'broadcast')""",
                (customer["id"], message),
            )

        sent += 1
        recipients.append(phone)

    return {"sent": sent, "failed": failed, "recipients": recipients}


def get_broadcast_history(db_path: str | Path, limit: int = 20) -> list[dict[str, Any]]:
    """Return recent broadcast messages."""
    with get_db(db_path) as conn:
        rows = conn.execute(
            """SELECT m.*, c.name, c.phone
               FROM whatsapp_messages m
               LEFT JOIN customers c ON c.id = m.customer_id
               WHERE m.message_type = 'broadcast'
               ORDER BY m.timestamp DESC
               LIMIT ?""",
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]
