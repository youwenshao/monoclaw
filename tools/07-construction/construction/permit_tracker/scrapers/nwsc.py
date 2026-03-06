"""New Works / Street Construction (NWSC) permit tracker.

Checks road opening permit (XP) and excavation permit status with the
Highways Department and relevant district lands offices.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

logger = logging.getLogger("openclaw.construction.permit_tracker.scrapers.nwsc")

HYD_BASE_URL = "https://www.hyd.gov.hk"
XP_STATUS_URL = f"{HYD_BASE_URL}/en/road-and-railway/road-works/excavation-permits"
REQUEST_TIMEOUT = 30
MAX_RETRIES = 3
INITIAL_BACKOFF = 2.0


async def check_nwsc_status(reference: str) -> dict[str, Any]:
    """Check the status of a road opening / excavation permit.

    Args:
        reference: The NWSC or XP reference number.

    Returns:
        Dict with keys: reference, status, status_date, details, permit_type.
    """
    for attempt in range(MAX_RETRIES):
        try:
            return await _fetch_nwsc_status(reference)
        except Exception as exc:
            wait = INITIAL_BACKOFF * (2 ** attempt)
            logger.warning(
                "NWSC check attempt %d/%d for %s failed (%s), retrying in %.1fs",
                attempt + 1, MAX_RETRIES, reference, exc, wait,
            )
            if attempt < MAX_RETRIES - 1:
                await asyncio.sleep(wait)

    logger.error("Exhausted retries checking NWSC reference %s", reference)
    return _mock_nwsc_status(reference)


async def _fetch_nwsc_status(reference: str) -> dict[str, Any]:
    try:
        import httpx
    except ImportError:
        logger.warning("httpx not installed — using mock NWSC data")
        return _mock_nwsc_status(reference)

    try:
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            resp = await client.get(
                XP_STATUS_URL,
                params={"ref": reference},
                headers={"User-Agent": "MonoClaw PermitTracker/1.0"},
            )
            if resp.status_code == 200:
                return _parse_nwsc_response(reference, resp.text)
    except Exception:
        logger.exception("NWSC HTTP request failed for %s", reference)

    return _mock_nwsc_status(reference)


def _parse_nwsc_response(reference: str, html: str) -> dict[str, Any]:
    """Extract permit info from the HyD response page."""
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        logger.warning("beautifulsoup4 not installed — returning raw data")
        return _mock_nwsc_status(reference)

    soup = BeautifulSoup(html, "html.parser")

    status = "Unknown"
    status_date = None
    details = ""
    permit_type = "excavation_permit"

    status_el = (
        soup.find(string=lambda s: s and "status" in s.lower())
        if soup.find(string=lambda s: s and "status" in s.lower())
        else None
    )
    if status_el:
        parent = status_el.find_parent("tr") or status_el.find_parent("div")
        if parent:
            cells = parent.find_all("td")
            if len(cells) >= 2:
                status = cells[1].get_text(strip=True)

    date_el = soup.find(string=lambda s: s and "date" in s.lower())
    if date_el:
        parent = date_el.find_parent("tr") or date_el.find_parent("div")
        if parent:
            cells = parent.find_all("td")
            if len(cells) >= 2:
                status_date = cells[1].get_text(strip=True)

    ref_upper = reference.upper()
    if "XP" in ref_upper:
        permit_type = "excavation_permit"
    elif "ROP" in ref_upper:
        permit_type = "road_opening_permit"
    elif "TTA" in ref_upper:
        permit_type = "temporary_traffic_arrangement"

    return {
        "reference": reference,
        "status": status,
        "status_date": status_date,
        "details": details,
        "permit_type": permit_type,
        "mock": False,
    }


def _mock_nwsc_status(reference: str) -> dict[str, Any]:
    logger.debug("Returning mock NWSC data for %s", reference)
    return {
        "reference": reference,
        "status": "Unknown",
        "status_date": None,
        "details": "Live NWSC portal unavailable — using mock data",
        "permit_type": "excavation_permit",
        "mock": True,
    }
