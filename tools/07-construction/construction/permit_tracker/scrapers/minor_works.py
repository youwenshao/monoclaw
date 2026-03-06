"""Minor Works Control System (MWCS) status checker.

Handles Class I, II, and III minor works submissions with class-specific
timeline expectations per the Buildings Ordinance (Cap. 123).
"""

from __future__ import annotations

import asyncio
import logging
from datetime import date, timedelta
from typing import Any

logger = logging.getLogger("openclaw.construction.permit_tracker.scrapers.minor_works")

MWCS_BASE_URL = "https://www.bd.gov.hk/en/resources/online-tools/minor-works"

TIMELINE_DAYS: dict[str, dict[str, int]] = {
    "I": {
        "acknowledgement": 7,
        "approval": 42,
        "description": "Requires AP/RSE; BD vets plans before commencement",
    },
    "II": {
        "acknowledgement": 7,
        "approval": 28,
        "description": "Simplified procedure; appointed prescribed registered contractor",
    },
    "III": {
        "acknowledgement": 7,
        "approval": 14,
        "description": "Designated workers; notification to BD within 14 days after completion",
    },
}


async def check_minor_works_status(
    reference: str,
    mw_class: str,
) -> dict[str, Any]:
    """Query the Minor Works status for a given reference.

    Args:
        reference: The MW reference number (e.g. MW/2024/1234).
        mw_class: One of 'I', 'II', or 'III'.

    Returns:
        Dict with status info and class-specific timeline expectations.
    """
    mw_class = mw_class.upper().strip()
    if mw_class not in TIMELINE_DAYS:
        logger.warning("Unknown minor works class '%s', defaulting to I", mw_class)
        mw_class = "I"

    timeline_config = TIMELINE_DAYS[mw_class]

    try:
        result = await _fetch_mwcs_status(reference)
    except Exception:
        logger.exception("MWCS status check failed for %s", reference)
        result = _mock_mwcs_status(reference)

    result["mw_class"] = mw_class
    result["expected_acknowledgement_days"] = timeline_config["acknowledgement"]
    result["expected_approval_days"] = timeline_config["approval"]
    result["class_description"] = timeline_config["description"]

    return result


async def _fetch_mwcs_status(reference: str) -> dict[str, Any]:
    """Attempt a live lookup against the BD minor works portal."""
    try:
        import httpx
    except ImportError:
        logger.warning("httpx not installed — using mock MWCS data")
        return _mock_mwcs_status(reference)

    url = f"{MWCS_BASE_URL}/check-status"
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(url, params={"ref": reference})
            if resp.status_code == 200:
                from construction.permit_tracker.scrapers.parser import (
                    parse_bd_status_page,
                    parse_status_label,
                )
                parsed = parse_bd_status_page(resp.text)
                if parsed.get("status") and parsed["status"] != "Unknown":
                    return parsed
    except Exception:
        logger.exception("MWCS HTTP request failed for %s", reference)

    return _mock_mwcs_status(reference)


def _mock_mwcs_status(reference: str) -> dict[str, Any]:
    logger.debug("Returning mock MWCS data for %s", reference)
    return {
        "reference": reference,
        "status": "Unknown",
        "status_date": None,
        "details": "Live MWCS portal unavailable — using mock data",
        "mock": True,
    }


def expected_completion_for_class(
    mw_class: str,
    submitted_date: date | str,
) -> date:
    """Calculate expected completion date based on minor works class."""
    if isinstance(submitted_date, str):
        submitted_date = date.fromisoformat(submitted_date[:10])

    mw_class = mw_class.upper().strip()
    days = TIMELINE_DAYS.get(mw_class, TIMELINE_DAYS["I"])["approval"]
    return submitted_date + timedelta(days=days)
