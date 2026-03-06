"""Soft blacklist management with configurable thresholds and cooldown."""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import Any

from openclaw_shared.database import get_db
from openclaw_shared.mona_events import emit_event

logger = logging.getLogger("openclaw.fnb.no-show-shield.blacklist")

DEFAULT_NO_SHOW_THRESHOLD = 3
DEFAULT_COOLDOWN_DAYS = 180
DEFAULT_DEPOSIT_AMOUNT_HKD = 200


def check_and_blacklist(
    db_path: str,
    phone: str,
    no_show_threshold: int = DEFAULT_NO_SHOW_THRESHOLD,
) -> bool:
    """Check if a guest should be blacklisted based on no-show count.

    Automatically blacklists if threshold is met. Returns True if blacklisted.
    """
    with get_db(db_path) as conn:
        row = conn.execute(
            "SELECT no_shows, is_blacklisted FROM guests WHERE phone = ?",
            (phone,),
        ).fetchone()

    if not row:
        return False

    guest = dict(row)
    if guest["is_blacklisted"]:
        return True

    if (guest["no_shows"] or 0) >= no_show_threshold:
        with get_db(db_path) as conn:
            conn.execute(
                """UPDATE guests SET is_blacklisted = TRUE, blacklisted_at = CURRENT_TIMESTAMP
                   WHERE phone = ?""",
                (phone,),
            )

        emit_event(
            db_path,
            event_type="alert",
            tool_name="no-show-shield",
            summary=f"Guest {phone} auto-blacklisted after {guest['no_shows']} no-shows",
            requires_human_action=True,
        )

        logger.warning("Guest %s blacklisted (%d no-shows)", phone, guest["no_shows"])
        return True

    return False


def is_blacklisted(db_path: str, phone: str) -> bool:
    """Check if a guest is currently blacklisted."""
    with get_db(db_path) as conn:
        row = conn.execute(
            "SELECT is_blacklisted FROM guests WHERE phone = ?",
            (phone,),
        ).fetchone()
    return bool(row and row["is_blacklisted"])


def toggle_blacklist(db_path: str, phone: str) -> dict[str, Any]:
    """Toggle blacklist status for a guest. Returns updated state."""
    with get_db(db_path) as conn:
        row = conn.execute(
            "SELECT is_blacklisted, name FROM guests WHERE phone = ?",
            (phone,),
        ).fetchone()

    if not row:
        return {"error": "Guest not found", "phone": phone}

    current = bool(row["is_blacklisted"])
    new_status = not current

    with get_db(db_path) as conn:
        if new_status:
            conn.execute(
                """UPDATE guests SET is_blacklisted = TRUE, blacklisted_at = CURRENT_TIMESTAMP
                   WHERE phone = ?""",
                (phone,),
            )
        else:
            conn.execute(
                "UPDATE guests SET is_blacklisted = FALSE, blacklisted_at = NULL WHERE phone = ?",
                (phone,),
            )

    action = "blacklisted" if new_status else "removed from blacklist"
    emit_event(
        db_path,
        event_type="info",
        tool_name="no-show-shield",
        summary=f"Guest {row['name'] or phone} manually {action}",
    )

    return {
        "phone": phone,
        "name": row["name"],
        "is_blacklisted": new_status,
        "action": action,
    }


def list_blacklisted(db_path: str) -> list[dict[str, Any]]:
    """List all blacklisted guests."""
    with get_db(db_path) as conn:
        rows = conn.execute(
            """SELECT * FROM guests
               WHERE is_blacklisted = TRUE
               ORDER BY blacklisted_at DESC"""
        ).fetchall()
    return [dict(r) for r in rows]


def check_cooldown_expired(
    db_path: str,
    phone: str,
    cooldown_days: int = DEFAULT_COOLDOWN_DAYS,
) -> bool:
    """Check if a blacklisted guest's cooldown period has expired."""
    with get_db(db_path) as conn:
        row = conn.execute(
            "SELECT is_blacklisted, blacklisted_at FROM guests WHERE phone = ?",
            (phone,),
        ).fetchone()

    if not row or not row["is_blacklisted"] or not row["blacklisted_at"]:
        return False

    try:
        blacklisted_at = datetime.fromisoformat(row["blacklisted_at"])
    except (ValueError, TypeError):
        return False

    return datetime.now() - blacklisted_at > timedelta(days=cooldown_days)


def auto_remove_expired(
    db_path: str,
    cooldown_days: int = DEFAULT_COOLDOWN_DAYS,
) -> list[str]:
    """Remove blacklist from guests whose cooldown has expired. Returns list of phones."""
    cutoff = (datetime.now() - timedelta(days=cooldown_days)).isoformat()
    removed: list[str] = []

    with get_db(db_path) as conn:
        rows = conn.execute(
            """SELECT phone, name FROM guests
               WHERE is_blacklisted = TRUE AND blacklisted_at < ?""",
            (cutoff,),
        ).fetchall()

        for row in rows:
            conn.execute(
                "UPDATE guests SET is_blacklisted = FALSE, blacklisted_at = NULL WHERE phone = ?",
                (row["phone"],),
            )
            removed.append(row["phone"])

    if removed:
        emit_event(
            db_path,
            event_type="info",
            tool_name="no-show-shield",
            summary=f"Auto-removed {len(removed)} guests from blacklist (cooldown expired)",
        )
        logger.info("Auto-removed %d guests from blacklist", len(removed))

    return removed


def requires_deposit(
    db_path: str,
    phone: str,
    no_show_threshold: int = DEFAULT_NO_SHOW_THRESHOLD,
) -> dict[str, Any]:
    """Determine if a guest requires a deposit for their booking.

    Deposit is required if:
    - Guest is blacklisted, OR
    - Guest has no-shows >= threshold - 1 (one more no-show = blacklist)
    """
    with get_db(db_path) as conn:
        row = conn.execute(
            "SELECT no_shows, is_blacklisted, reliability_score FROM guests WHERE phone = ?",
            (phone,),
        ).fetchone()

    if not row:
        return {"required": False, "reason": None, "amount": 0}

    guest = dict(row)

    if guest["is_blacklisted"]:
        return {
            "required": True,
            "reason": "blacklisted",
            "amount": DEFAULT_DEPOSIT_AMOUNT_HKD * 2,
        }

    if (guest["no_shows"] or 0) >= no_show_threshold - 1:
        return {
            "required": True,
            "reason": "high_risk",
            "amount": DEFAULT_DEPOSIT_AMOUNT_HKD,
        }

    if guest["reliability_score"] == "D":
        return {
            "required": True,
            "reason": "low_reliability",
            "amount": DEFAULT_DEPOSIT_AMOUNT_HKD,
        }

    return {"required": False, "reason": None, "amount": 0}
