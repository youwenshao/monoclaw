"""Human handoff / escalation logic for the ClientPortal Bot."""

from __future__ import annotations

import logging
from datetime import datetime, time as dt_time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from openclaw_shared.database import get_db

logger = logging.getLogger("openclaw.immigration.bot.escalation")

HKT = ZoneInfo("Asia/Hong_Kong")

ESCALATION_KEYWORDS = {
    "speak to someone", "talk to a person", "human", "consultant",
    "lawyer", "manager", "complaint", "frustrated", "angry", "urgent",
    "legal advice", "appeal", "refusal", "refused", "rejected",
    "不滿", "投訴", "顧問", "律師", "人工", "拒絕", "上訴",
}

MAX_BOT_TURNS_BEFORE_ESCALATION = 6


def should_escalate(intent: str, message: str, conversation_history: list[dict]) -> bool:
    """Determine whether the conversation should be handed off to a human.

    Escalation triggers:
    - Intent is explicitly "escalation"
    - Message contains escalation keywords
    - Bot has replied more than MAX_BOT_TURNS_BEFORE_ESCALATION times without resolution
    """
    if intent == "escalation":
        return True

    message_lower = message.lower()
    for keyword in ESCALATION_KEYWORDS:
        if keyword in message_lower:
            return True

    bot_turns = sum(1 for m in conversation_history if m.get("sender") == "bot")
    if bot_turns >= MAX_BOT_TURNS_BEFORE_ESCALATION:
        return True

    return False


def escalate_to_consultant(
    case: dict,
    conversation: list[dict],
    db_path: Any,
) -> None:
    """Flag the conversation as escalated so a consultant can pick it up."""
    case_id = case.get("id")
    if case_id is None:
        logger.warning("Cannot escalate — no case_id for phone=%s", case.get("phone"))
        return

    with get_db(db_path) as conn:
        conn.execute(
            "UPDATE conversations SET escalated = 1 WHERE case_id = ? AND escalated = 0",
            (case_id,),
        )

    logger.info("Case %s escalated to consultant", case.get("reference_code", case_id))


def is_business_hours(now: datetime | None = None) -> bool:
    """Check if the current time is within HK business hours.

    Mon-Fri 9:00-18:00, Sat 9:00-13:00, Sun & holidays closed.
    """
    if now is None:
        now = datetime.now(HKT)
    elif now.tzinfo is None:
        now = now.replace(tzinfo=HKT)

    weekday = now.weekday()  # 0=Mon, 6=Sun

    if weekday == 6:
        return False

    current_time = now.time()

    if weekday == 5:  # Saturday
        return dt_time(9, 0) <= current_time < dt_time(13, 0)

    return dt_time(9, 0) <= current_time < dt_time(18, 0)


def next_business_open(now: datetime | None = None) -> datetime:
    """Return the next datetime when the office opens (HKT)."""
    if now is None:
        now = datetime.now(HKT)
    elif now.tzinfo is None:
        now = now.replace(tzinfo=HKT)

    if is_business_hours(now):
        return now

    candidate = now.replace(hour=9, minute=0, second=0, microsecond=0)
    if candidate <= now:
        candidate += timedelta(days=1)

    while candidate.weekday() == 6:
        candidate += timedelta(days=1)

    return candidate
