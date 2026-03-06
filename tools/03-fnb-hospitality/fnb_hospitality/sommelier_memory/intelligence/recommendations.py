"""LLM-powered preference summarizer from structured guest data."""

from __future__ import annotations

import logging
from typing import Any

from openclaw_shared.llm.base import LLMProvider

logger = logging.getLogger("openclaw.fnb-hospitality.sommelier-memory.recommendations")

SUMMARIZE_SYSTEM_PROMPT = """\
You are a sommelier and dining concierge at an upscale Hong Kong restaurant.
Given structured guest preference data, write a concise natural-language summary
(3-5 sentences) that a server can quickly scan before service.

Focus on:
- Key food and drink preferences (wines, teas, spirits)
- Dietary restrictions and allergies (highlight severity)
- Seating and ambiance preferences
- Any patterns from visit history

Be warm but professional. Use specific details from the data provided.
"""


def _format_guest_data_prompt(guest_data: dict[str, Any]) -> str:
    """Format structured guest data into an LLM-readable prompt."""
    lines = [f"Guest: {guest_data.get('name', 'Unknown')}"]

    if guest_data.get("preferred_name"):
        lines.append(f"Preferred name: {guest_data['preferred_name']}")

    lines.append(f"VIP tier: {guest_data.get('vip_tier', 'regular')}")
    lines.append(f"Total visits: {guest_data.get('total_visits', 0)}")

    if guest_data.get("dietary_info"):
        lines.append("\nDietary information:")
        for d in guest_data["dietary_info"]:
            severity = f" [{d['severity']}]" if d.get("severity") else ""
            notes = f" — {d['notes']}" if d.get("notes") else ""
            lines.append(f"  - {d['type']}: {d['item']}{severity}{notes}")

    if guest_data.get("preferences"):
        lines.append("\nPreferences:")
        for p in guest_data["preferences"]:
            lines.append(f"  - {p['category']}: {p['preference']} ({p.get('strength', 'like')})")

    if guest_data.get("recent_visits"):
        lines.append("\nRecent visits:")
        for v in guest_data["recent_visits"][:5]:
            visit_line = f"  - {v.get('visit_date', '?')}: party of {v.get('party_size', '?')}, HK${v.get('total_spend', 0):,.0f}"
            if v.get("wine_orders"):
                visit_line += f" | Wine: {v['wine_orders']}"
            if v.get("food_highlights"):
                visit_line += f" | Highlights: {v['food_highlights']}"
            lines.append(visit_line)

    if guest_data.get("notes"):
        lines.append(f"\nStaff notes: {guest_data['notes']}")

    return "\n".join(lines)


async def summarize_preferences(
    guest_data: dict[str, Any],
    llm_provider: LLMProvider,
) -> str:
    """Generate a natural language summary of a guest's preferences using LLM.

    Falls back to a formatted text summary if LLM generation fails.
    """
    prompt = _format_guest_data_prompt(guest_data)

    try:
        summary = await llm_provider.generate(
            prompt,
            system=SUMMARIZE_SYSTEM_PROMPT,
            max_tokens=250,
            temperature=0.6,
        )
        return summary.strip()
    except Exception:
        logger.warning(
            "LLM summarization failed for guest '%s', using fallback",
            guest_data.get("name", "unknown"),
        )
        return _fallback_summary(guest_data)


def _fallback_summary(guest_data: dict[str, Any]) -> str:
    """Plain-text fallback when no LLM is available."""
    parts: list[str] = []
    name = guest_data.get("preferred_name") or guest_data.get("name", "Guest")
    tier = guest_data.get("vip_tier", "regular").upper()
    parts.append(f"{name} is a {tier} guest with {guest_data.get('total_visits', 0)} visits.")

    allergies = [
        d for d in guest_data.get("dietary_info", [])
        if d.get("type") in ("allergy", "intolerance")
    ]
    if allergies:
        items = [f"{a['item']} ({a.get('severity', 'unknown')})" for a in allergies]
        parts.append(f"Allergies: {', '.join(items)}.")

    wine_prefs = [
        p for p in guest_data.get("preferences", [])
        if p.get("category") in ("wine", "spirit", "cocktail")
    ]
    if wine_prefs:
        items = [f"{p['preference']}" for p in wine_prefs]
        parts.append(f"Drinks: {', '.join(items)}.")

    tea_prefs = [
        p for p in guest_data.get("preferences", [])
        if p.get("category") == "tea"
    ]
    if tea_prefs:
        parts.append(f"Tea: {', '.join(p['preference'] for p in tea_prefs)}.")

    return " ".join(parts)
