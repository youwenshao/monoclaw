"""Daily safety checklist conversation flow via WhatsApp."""

from __future__ import annotations

import logging
from datetime import date
from typing import Any

from openclaw_shared.database import get_db
from openclaw_shared.mona_events import emit_event

logger = logging.getLogger("openclaw.construction.safety_form.bot.checklist")

CATEGORIES_ORDER = [
    "housekeeping",
    "ppe",
    "scaffolding",
    "excavation",
    "lifting",
    "fire_precautions",
]

CATEGORY_LABELS = {
    "housekeeping": "🧹 Housekeeping",
    "ppe": "🦺 PPE Compliance",
    "scaffolding": "🪜 Scaffolding",
    "excavation": "⛏️ Excavation",
    "lifting": "🏗️ Lifting Operations",
    "fire_precautions": "🔥 Fire Precautions",
}

# In-memory session tracking: sender -> session state
_sessions: dict[str, dict[str, Any]] = {}


async def send_morning_checklist(app_state: Any, site_id: int) -> None:
    """Send the morning checklist prompt to the site's safety officer via WhatsApp."""
    from construction.safety_form.bot.whatsapp_handler import send_whatsapp_message, _get_messaging_config

    db_path = app_state.db_paths["safety_form"]
    messaging_cfg = _get_messaging_config(app_state)

    with get_db(db_path) as conn:
        site = conn.execute("SELECT * FROM sites WHERE id = ?", (site_id,)).fetchone()
        if not site:
            logger.error("Site %d not found", site_id)
            return

    officer_phone = dict(site).get("safety_officer", "")
    if not officer_phone:
        logger.warning("No safety officer phone for site %d", site_id)
        return

    session = {
        "site_id": site_id,
        "site_name": site["site_name"],
        "current_category_idx": 0,
        "items_checked": [],
        "started_at": date.today().isoformat(),
    }
    _sessions[officer_phone] = session

    first_cat = CATEGORIES_ORDER[0]
    label = CATEGORY_LABELS.get(first_cat, first_cat)

    message = (
        f"Good morning! 🌅\n"
        f"Daily safety inspection for *{site['site_name']}*\n"
        f"Date: {date.today().isoformat()}\n\n"
        f"Let's begin with *{label}*\n"
        f"Reply: PASS / FAIL / NA for each area.\n"
        f"You can also attach photos."
    )

    sent = await send_whatsapp_message(officer_phone, message, messaging_cfg)
    if sent:
        logger.info("Morning checklist sent to %s for site %d", officer_phone, site_id)
        emit_event(
            app_state.db_paths["mona_events"],
            event_type="action_started",
            tool_name="safety-form",
            summary=f"Morning checklist sent to site #{site_id}",
        )


async def process_checklist_response(
    app_state: Any,
    sender: str,
    message: str,
    media_url: str | None,
) -> dict:
    """Process a checklist response message from a site officer.

    Returns a dict with 'reply' text and optional 'completed' flag.
    """
    session = _sessions.get(sender)
    if not session:
        return {"reply": "No active checklist session. Ask your admin to send today's checklist."}

    status = _parse_status(message)
    cat_idx = session["current_category_idx"]

    if cat_idx >= len(CATEGORIES_ORDER):
        return {"reply": "Checklist already completed for today. ✅"}

    category = CATEGORIES_ORDER[cat_idx]
    label = CATEGORY_LABELS.get(category, category)

    session["items_checked"].append({
        "category": category,
        "status": status,
        "notes": message if status == "fail" else "",
        "has_photo": media_url is not None,
    })

    session["current_category_idx"] = cat_idx + 1

    if session["current_category_idx"] >= len(CATEGORIES_ORDER):
        summary = _build_summary(session)
        _save_bot_inspection(app_state, session)
        del _sessions[sender]
        return {
            "reply": f"✅ Checklist complete!\n\n{summary}",
            "completed": True,
        }

    next_cat = CATEGORIES_ORDER[session["current_category_idx"]]
    next_label = CATEGORY_LABELS.get(next_cat, next_cat)

    status_icon = {"pass": "✅", "fail": "❌", "na": "➖"}.get(status, "❓")
    return {
        "reply": (
            f"{status_icon} {label}: *{status.upper()}*\n\n"
            f"Next: *{next_label}*\n"
            f"Reply: PASS / FAIL / NA"
        ),
    }


def _parse_status(message: str) -> str:
    """Parse a status keyword from the user's message."""
    lower = message.lower().strip()
    if lower in ("pass", "ok", "yes", "good", "done", "check", "checked", "y"):
        return "pass"
    if lower in ("fail", "bad", "no", "unsafe", "n"):
        return "fail"
    if lower in ("na", "n/a", "not applicable", "skip"):
        return "na"
    if "fail" in lower or "bad" in lower or "unsafe" in lower:
        return "fail"
    if "pass" in lower or "ok" in lower or "good" in lower:
        return "pass"
    return "pass"


def _build_summary(session: dict) -> str:
    """Build a text summary of the completed checklist."""
    lines = []
    pass_count = 0
    fail_count = 0
    for item in session["items_checked"]:
        cat = item["category"]
        label = CATEGORY_LABELS.get(cat, cat)
        status = item["status"]
        icon = {"pass": "✅", "fail": "❌", "na": "➖"}.get(status, "❓")
        lines.append(f"{icon} {label}: {status.upper()}")
        if status == "pass":
            pass_count += 1
        elif status == "fail":
            fail_count += 1

    total = len(session["items_checked"])
    applicable = total - sum(1 for i in session["items_checked"] if i["status"] == "na")
    score = (pass_count / applicable * 100) if applicable else 0

    lines.append(f"\nScore: {score:.0f}% ({pass_count}/{applicable})")
    if fail_count:
        lines.append(f"⚠️ {fail_count} item(s) need attention")
    return "\n".join(lines)


def _save_bot_inspection(app_state: Any, session: dict) -> None:
    """Persist the bot-collected checklist to the database."""
    db_path = app_state.db_paths["safety_form"]
    try:
        with get_db(db_path) as conn:
            cursor = conn.execute(
                "INSERT INTO daily_inspections (site_id, inspection_date, inspector, status) "
                "VALUES (?, ?, 'WhatsApp Bot', 'completed')",
                (session["site_id"], session["started_at"]),
            )
            inspection_id = cursor.lastrowid

            for item in session["items_checked"]:
                conn.execute(
                    "INSERT INTO checklist_items (inspection_id, category, item_description, status, notes) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (inspection_id, item["category"], f"{item['category']} — bot check",
                     item["status"], item.get("notes", "")),
                )

        logger.info("Bot inspection #%d saved for site %d", inspection_id, session["site_id"])
    except Exception:
        logger.exception("Failed to save bot inspection for site %d", session["site_id"])
