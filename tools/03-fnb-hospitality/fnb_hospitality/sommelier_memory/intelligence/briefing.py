"""Pre-service briefing card generator with LLM-powered natural language summaries."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from openclaw_shared.database import get_db
from openclaw_shared.llm.base import LLMProvider

from fnb_hospitality.sommelier_memory.guests.profiles import get_guest
from fnb_hospitality.sommelier_memory.guests.history import calculate_lifetime_value, get_visit_history

logger = logging.getLogger("openclaw.fnb-hospitality.sommelier-memory.briefing")

BRIEFING_SYSTEM_PROMPT = """\
You are a professional maître d' assistant at a fine-dining restaurant in Hong Kong.
Generate a concise, warm pre-service briefing note for the service staff.
Use the guest data provided to craft 2-4 sentences covering:
- How to greet the guest (use preferred name if available)
- Key allergies or dietary needs (CRITICAL safety info first)
- Drink/wine/tea preferences
- VIP tier context and any special notes
Keep it natural, professional, and actionable. Mix English and Cantonese terms where appropriate.
"""


def _build_structured_briefing(guest: dict[str, Any], ltv: dict[str, Any]) -> dict[str, Any]:
    """Assemble the structured data portion of the briefing card."""
    allergies = [
        d for d in guest.get("dietary_info", [])
        if d.get("type") in ("allergy", "intolerance")
    ]
    dietary_prefs = [
        d for d in guest.get("dietary_info", [])
        if d.get("type") in ("preference", "restriction")
    ]
    wine_prefs = [
        p for p in guest.get("preferences", [])
        if p.get("category") in ("wine", "spirit", "cocktail")
    ]
    tea_prefs = [
        p for p in guest.get("preferences", [])
        if p.get("category") == "tea"
    ]
    seating_prefs = [
        p for p in guest.get("preferences", [])
        if p.get("category") == "seating"
    ]

    return {
        "guest_id": guest["id"],
        "name": guest.get("name", ""),
        "preferred_name": guest.get("preferred_name", ""),
        "phone": guest.get("phone", ""),
        "language_pref": guest.get("language_pref", "cantonese"),
        "vip_tier": guest.get("vip_tier", "regular"),
        "last_visit": guest.get("last_visit"),
        "total_visits": ltv.get("visit_count", 0),
        "total_spend": ltv.get("total_spend", 0),
        "avg_per_head": ltv.get("avg_per_head", 0),
        "allergies": [
            {"item": a["item"], "severity": a.get("severity", "unknown"), "notes": a.get("notes", "")}
            for a in allergies
        ],
        "dietary_preferences": [
            {"item": d["item"], "notes": d.get("notes", "")}
            for d in dietary_prefs
        ],
        "wine_preferences": [
            {"preference": p["preference"], "strength": p.get("strength", "like")}
            for p in wine_prefs
        ],
        "tea_preferences": [
            {"preference": p["preference"], "strength": p.get("strength", "like")}
            for p in tea_prefs
        ],
        "seating_preferences": [
            {"preference": p["preference"]}
            for p in seating_prefs
        ],
        "celebrations": guest.get("celebrations", []),
        "tags": guest.get("tags", ""),
        "notes": guest.get("notes", ""),
    }


def _format_briefing_prompt(structured: dict[str, Any], recent_visits: list[dict[str, Any]]) -> str:
    lines = [f"Guest: {structured['name']}"]
    if structured["preferred_name"]:
        lines.append(f"Preferred name: {structured['preferred_name']}")
    lines.append(f"VIP tier: {structured['vip_tier'].upper()}")
    lines.append(f"Language: {structured['language_pref']}")
    lines.append(f"Total visits: {structured['total_visits']}, Lifetime spend: HK${structured['total_spend']:,.0f}")

    if structured.get("last_visit"):
        lines.append(f"Last visit: {structured['last_visit']}")

    if structured["allergies"]:
        allergy_parts = [
            f"  - {a['item']} ({a['severity']})" + (f" — {a['notes']}" if a["notes"] else "")
            for a in structured["allergies"]
        ]
        lines.append("ALLERGIES (CRITICAL):\n" + "\n".join(allergy_parts))

    if structured["dietary_preferences"]:
        lines.append("Dietary: " + ", ".join(d["item"] for d in structured["dietary_preferences"]))

    if structured["wine_preferences"]:
        lines.append("Wine/spirits: " + ", ".join(
            f"{w['preference']} ({w['strength']})" for w in structured["wine_preferences"]
        ))

    if structured["tea_preferences"]:
        lines.append("Tea: " + ", ".join(t["preference"] for t in structured["tea_preferences"]))

    if structured["seating_preferences"]:
        lines.append("Seating: " + ", ".join(s["preference"] for s in structured["seating_preferences"]))

    if recent_visits:
        last = recent_visits[0]
        lines.append(f"Most recent order highlights: {last.get('food_highlights', 'N/A')}")
        if last.get("wine_orders"):
            lines.append(f"Last wine order: {last['wine_orders']}")

    if structured["notes"]:
        lines.append(f"Staff notes: {structured['notes']}")

    return "\n".join(lines)


async def generate_briefing(
    db_path: str | Path,
    guest_id: int,
    llm_provider: LLMProvider | None = None,
) -> dict[str, Any]:
    """Generate a full briefing card for a single guest.

    Returns structured data plus an LLM-generated natural_language_summary
    (falls back to a formatted text summary if no LLM is available).
    """
    guest = get_guest(db_path, guest_id)
    if not guest:
        raise ValueError(f"Guest {guest_id} not found")

    ltv = calculate_lifetime_value(db_path, guest_id)
    recent_visits = get_visit_history(db_path, guest_id, limit=3)
    structured = _build_structured_briefing(guest, ltv)
    prompt_text = _format_briefing_prompt(structured, recent_visits)

    if llm_provider:
        try:
            summary = await llm_provider.generate(
                prompt_text,
                system=BRIEFING_SYSTEM_PROMPT,
                max_tokens=300,
                temperature=0.6,
            )
        except Exception:
            logger.warning("LLM briefing generation failed for guest #%d, using fallback", guest_id)
            summary = prompt_text
    else:
        summary = prompt_text

    structured["natural_language_summary"] = summary
    structured["recent_visits"] = recent_visits

    return structured


async def generate_service_briefings(
    db_path: str | Path,
    booking_date: str,
    llm_provider: LLMProvider | None = None,
) -> list[dict[str, Any]]:
    """Generate briefings for all guests with bookings on a given date.

    Cross-references the bookings table (TableMaster) with sm_guests by phone number.
    Falls back to listing all sm_guests if no booking DB is available.
    """
    guest_ids: list[int] = []

    with get_db(db_path) as conn:
        rows = conn.execute(
            """SELECT DISTINCT sg.id
               FROM sm_guests sg
               WHERE sg.phone IN (
                   SELECT DISTINCT guest_phone FROM bookings
                   WHERE booking_date = ? AND status IN ('confirmed', 'pending')
               )""",
            (booking_date,),
        ).fetchall()
        guest_ids = [r[0] for r in rows]

    if not guest_ids:
        with get_db(db_path) as conn:
            rows = conn.execute(
                """SELECT DISTINCT sg.id FROM sm_guests sg
                   INNER JOIN visits v ON v.guest_id = sg.id
                   WHERE v.visit_date = ?""",
                (booking_date,),
            ).fetchall()
            guest_ids = [r[0] for r in rows]

    briefings = []
    for gid in guest_ids:
        try:
            briefing = await generate_briefing(db_path, gid, llm_provider)
            briefings.append(briefing)
        except Exception:
            logger.warning("Failed to generate briefing for guest #%d", gid, exc_info=True)

    return briefings
