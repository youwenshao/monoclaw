"""Deed of Mutual Covenant (DMC) responsibility resolution.

Determines whether the Owner's Corporation (OC), individual owner, or
management company is responsible for a defect based on HK building
management conventions.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from openclaw_shared.database import get_db

logger = logging.getLogger("openclaw.construction.defects_manager.defects.dmc_resolver")


def get_default_matrix() -> dict[str, dict[str, str]]:
    """Return the default responsibility matrix.

    Each key is a defect category; values contain ``responsibility`` and
    ``notes`` fields.  Used for the DMC matrix partial in the dashboard.
    """
    return {
        "water_seepage": {
            "responsibility": "investigation_required",
            "notes": (
                "Responsibility depends on source. If from common area pipe — OC/management. "
                "If from upper unit — upper unit owner. Joint investigation recommended per "
                "Buildings Department practice."
            ),
        },
        "concrete_spalling": {
            "responsibility": "oc",
            "notes": "External walls and structural elements are common parts under DMC. OC responsible.",
        },
        "plumbing": {
            "responsibility": "varies",
            "notes": (
                "Pipes inside individual units — owner responsibility. "
                "Common drain stacks and risers — OC/management responsibility."
            ),
        },
        "electrical": {
            "responsibility": "varies",
            "notes": (
                "Wiring inside unit — owner. Common area electrical systems, "
                "main switchboard — OC/management."
            ),
        },
        "lift": {
            "responsibility": "oc",
            "notes": "Lifts are common parts. OC/management responsible for maintenance and repair.",
        },
        "window": {
            "responsibility": "owner",
            "notes": (
                "Windows belong to individual units under most DMCs. "
                "Owner responsible per Mandatory Window Inspection Scheme (MWIS)."
            ),
        },
        "common_area": {
            "responsibility": "oc",
            "notes": "Lobbies, corridors, staircases, and facilities are common parts. OC responsible.",
        },
        "structural": {
            "responsibility": "oc",
            "notes": (
                "Structural elements (columns, beams, slabs, load-bearing walls) are common parts. "
                "OC responsible. May require AP/RSE inspection under Buildings Ordinance."
            ),
        },
        "other": {
            "responsibility": "investigation_required",
            "notes": "Requires inspection to determine responsibility under DMC.",
        },
    }


def _is_inside_unit(location: str) -> bool:
    """Heuristic: decide if a location string refers to inside a unit."""
    lower = location.lower()
    unit_indicators = ["unit", "flat", "apartment", "room", "kitchen", "bathroom", "bedroom", "toilet"]
    return any(ind in lower for ind in unit_indicators)


def resolve_responsibility(
    property_id: int,
    category: str,
    location: str,
    db_path: str | Path | None = None,
) -> str:
    """Resolve who is responsible for a defect.

    Returns a string such as ``"oc"``, ``"owner"``, ``"management"``,
    ``"investigation_required"``, or ``"varies"``.
    """
    matrix = get_default_matrix()
    entry = matrix.get(category, matrix["other"])
    default_resp = entry["responsibility"]

    inside_unit = _is_inside_unit(location)

    if category == "plumbing":
        return "owner" if inside_unit else "oc"

    if category == "electrical":
        return "owner" if inside_unit else "oc"

    if category == "water_seepage":
        if inside_unit:
            return "investigation_required"
        return "oc"

    if category == "window":
        return "owner"

    if db_path and property_id:
        try:
            with get_db(db_path) as conn:
                prop = conn.execute(
                    "SELECT * FROM properties WHERE id = ?", (property_id,)
                ).fetchone()
                if prop and prop["property_name"]:
                    logger.debug("Resolving for property: %s", prop["property_name"])
        except Exception:
            logger.debug("Could not look up property %d", property_id)

    return default_resp
