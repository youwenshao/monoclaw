"""Innovation and Technology Fund (ITF) portal scraper for grant deadlines."""

from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import Any

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger("openclaw.academic.grant_tracker.monitoring.itf")

ITF_BASE_URL: str = "https://www.itf.gov.hk"
USER_AGENT = "MonoClaw GrantTracker/1.0"

KNOWN_ITF_PROGRAMMES: list[dict[str, str]] = [
    {
        "scheme_code": "ITF-ITSP",
        "scheme_name": "Innovation and Technology Support Programme",
        "path": "/en/funding-programmes/itsp/index.html",
        "description": "Supports applied R&D projects undertaken by universities, R&D centres, and industry.",
    },
    {
        "scheme_code": "ITF-UICP",
        "scheme_name": "University-Industry Collaboration Programme",
        "path": "/en/funding-programmes/uicp/index.html",
        "description": "Supports university-industry collaboration projects with cash contributions from industry sponsors.",
    },
    {
        "scheme_code": "ITF-PRP",
        "scheme_name": "Partnership Research Programme",
        "path": "/en/funding-programmes/prp/index.html",
        "description": "Supports collaborative R&D projects between industry and designated local public research institutions.",
    },
    {
        "scheme_code": "ITF-TCFS",
        "scheme_name": "Technology Co-operation Funding Scheme",
        "path": "/en/funding-programmes/tcfs/index.html",
        "description": "Supports projects promoting technology co-operation and exchange between HK and the Mainland/overseas.",
    },
    {
        "scheme_code": "ITF-SERAP",
        "scheme_name": "Strategic Research Areas Pilot",
        "path": "/en/funding-programmes/",
        "description": "Supports research in strategic areas identified by the government.",
    },
]


def _parse_date(text: str) -> str | None:
    text = text.strip()
    for fmt in ("%d %B %Y", "%d %b %Y", "%B %d, %Y", "%d/%m/%Y", "%d.%m.%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            continue
    match = re.search(r"(\d{1,2})[./\-](\d{1,2})[./\-](\d{4})", text)
    if match:
        try:
            d, m, y = match.groups()
            return datetime(int(y), int(m), int(d)).date().isoformat()
        except ValueError:
            pass
    return None


def _extract_deadlines_from_html(html: str, programme: dict[str, str]) -> list[dict[str, Any]]:
    soup = BeautifulSoup(html, "html.parser")
    results: list[dict[str, Any]] = []
    text = soup.get_text(" ", strip=True)

    deadline_patterns = [
        re.compile(r"deadline[:\s]*(\d{1,2}\s+\w+\s+\d{4})", re.IGNORECASE),
        re.compile(r"closing\s+date[:\s]*(\d{1,2}\s+\w+\s+\d{4})", re.IGNORECASE),
        re.compile(r"application\s+period.*?(?:to|until)\s+(\d{1,2}\s+\w+\s+\d{4})", re.IGNORECASE),
        re.compile(r"(\d{1,2}\s+(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4})", re.IGNORECASE),
    ]

    seen_dates: set[str] = set()
    for pattern in deadline_patterns:
        for match in pattern.finditer(text):
            raw = match.group(1) if match.lastindex else match.group(0)
            parsed = _parse_date(raw)
            if parsed and parsed not in seen_dates:
                seen_dates.add(parsed)
                results.append({
                    "scheme_name": programme["scheme_name"],
                    "scheme_code": programme["scheme_code"],
                    "deadline_date": parsed,
                    "call_url": ITF_BASE_URL + programme["path"],
                    "description": programme["description"],
                })

    return results


def scrape_itf_deadlines() -> list[dict]:
    """Fetch grant deadlines from the ITF portal.

    Scrapes each known ITF programme page for deadline dates.
    Returns a list of dicts with keys: scheme_name, scheme_code,
    deadline_date, call_url, description.
    """
    all_deadlines: list[dict] = []

    try:
        with httpx.Client(
            headers={"User-Agent": USER_AGENT},
            follow_redirects=True,
            timeout=30,
        ) as client:
            for programme in KNOWN_ITF_PROGRAMMES:
                url = ITF_BASE_URL + programme["path"]
                try:
                    resp = client.get(url)
                    resp.raise_for_status()
                    deadlines = _extract_deadlines_from_html(resp.text, programme)
                    all_deadlines.extend(deadlines)
                    logger.info(
                        "ITF %s: found %d deadline(s) from %s",
                        programme["scheme_code"], len(deadlines), url,
                    )
                except httpx.HTTPError as exc:
                    logger.warning("ITF %s: failed to fetch %s – %s", programme["scheme_code"], url, exc)
                    all_deadlines.append({
                        "scheme_name": programme["scheme_name"],
                        "scheme_code": programme["scheme_code"],
                        "deadline_date": None,
                        "call_url": url,
                        "description": programme["description"],
                    })

    except httpx.HTTPError as exc:
        logger.error("ITF scraper transport error: %s", exc)

    if not all_deadlines:
        logger.info("ITF scraper: no live deadlines found, returning programme metadata")
        for programme in KNOWN_ITF_PROGRAMMES:
            all_deadlines.append({
                "scheme_name": programme["scheme_name"],
                "scheme_code": programme["scheme_code"],
                "deadline_date": None,
                "call_url": ITF_BASE_URL + programme["path"],
                "description": programme["description"],
            })

    return all_deadlines
