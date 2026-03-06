"""WhatsApp dispatch for daily assignment delivery."""

from __future__ import annotations

import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from openclaw_shared.database import get_db

from construction.site_coordinator.dispatch.assignment_generator import generate_daily_brief

logger = logging.getLogger("openclaw.construction.site_coordinator.whatsapp_dispatcher")

_last_send_ts: float = 0.0


async def dispatch_assignments(
    db_path: str | Path,
    dispatch_date: str,
    app_state: Any,
) -> dict[str, Any]:
    """Send daily assignments to all contractors with work on *dispatch_date*.

    Evening dispatch (18:00 previous day) or morning reminder (07:00 same day)
    depending on when this is called.  Returns a summary dict.
    """
    with get_db(db_path) as conn:
        contractor_rows = conn.execute(
            "SELECT DISTINCT sa.contractor_id, c.company_name, c.whatsapp_number "
            "FROM schedule_assignments sa "
            "LEFT JOIN contractors c ON sa.contractor_id = c.id "
            "WHERE sa.assignment_date = ? "
            "AND sa.status NOT IN ('cancelled', 'rescheduled') "
            "AND c.whatsapp_number IS NOT NULL AND c.whatsapp_number != ''",
            (dispatch_date,),
        ).fetchall()

    contractors = [dict(r) for r in contractor_rows]
    messages_sent = 0
    failures = 0
    results: list[dict[str, Any]] = []

    config = _get_messaging_config(app_state)

    for c in contractors:
        brief = generate_daily_brief(db_path, c["contractor_id"], dispatch_date)
        if not brief:
            continue

        phone = c.get("whatsapp_number", "")
        success = await _send_whatsapp(phone, brief, config)

        if success:
            messages_sent += 1
            _mark_dispatched(db_path, c["contractor_id"], dispatch_date)
            results.append({"contractor_id": c["contractor_id"], "status": "sent"})
        else:
            failures += 1
            results.append({"contractor_id": c["contractor_id"], "status": "failed"})

    logger.info(
        "Dispatch for %s: %d sent, %d failed out of %d contractors",
        dispatch_date, messages_sent, failures, len(contractors),
    )
    return {
        "dispatch_date": dispatch_date,
        "messages_sent": messages_sent,
        "failures": failures,
        "details": results,
    }


def _get_messaging_config(app_state: Any) -> dict[str, str]:
    config = getattr(app_state, "config", None)
    if config is None:
        return {}
    messaging = getattr(config, "messaging", None)
    if messaging is None:
        return {}
    return {
        "twilio_account_sid": getattr(messaging, "twilio_account_sid", ""),
        "twilio_auth_token": getattr(messaging, "twilio_auth_token", ""),
        "twilio_whatsapp_from": getattr(messaging, "twilio_whatsapp_from", ""),
    }


async def _send_whatsapp(to: str, text: str, config: dict[str, str]) -> bool:
    """Send a WhatsApp message via Twilio with rate limiting."""
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
                data={"From": whatsapp_from, "To": whatsapp_to, "Body": text[:1600]},
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


def _mark_dispatched(db_path: str | Path, contractor_id: int, assignment_date: str) -> None:
    """Update assignment status to 'dispatched' with timestamp."""
    with get_db(db_path) as conn:
        conn.execute(
            "UPDATE schedule_assignments SET status = 'dispatched', dispatched_at = ? "
            "WHERE contractor_id = ? AND assignment_date = ? "
            "AND status NOT IN ('cancelled', 'rescheduled', 'completed')",
            (datetime.now().isoformat(), contractor_id, assignment_date),
        )
