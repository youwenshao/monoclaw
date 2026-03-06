"""RGC (Research Grants Council) website scraper for grant deadlines."""

from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import Any

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger("openclaw.academic.grant_tracker.monitoring.rgc")

RGC_BASE_URL: str = "https://www.ugc.edu.hk/eng/rgc/"
USER_AGENT = "MonoClaw GrantTracker/1.0"

KNOWN_SCHEMES: list[dict[str, str]] = [
    {
        "scheme_code": "GRF",
        "scheme_name": "General Research Fund",
        "path": "funding/grf/grf.html",
        "description": "Supports academic research across all disciplines in HK's UGC-funded institutions.",
    },
    {
        "scheme_code": "ECS",
        "scheme_name": "Early Career Scheme",
        "path": "funding/ecs/ecs.html",
        "description": "Supports junior faculty within first three years of appointment to conduct research.",
    },
    {
        "scheme_code": "CRF",
        "scheme_name": "Collaborative Research Fund",
        "path": "funding/crf/crf.html",
        "description": "Supports collaborative research involving researchers from at least two UGC-funded institutions.",
    },
    {
        "scheme_code": "TRS",
        "scheme_name": "Theme-based Research Scheme",
        "path": "funding/trs/trs.html",
        "description": "Supports large-scale strategic theme-based research projects addressing long-term HK needs.",
    },
    {
        "scheme_code": "RIF",
        "scheme_name": "Research Impact Fund",
        "path": "funding/rif/rif.html",
        "description": "Supports research projects with demonstrable social, economic, or environmental impact.",
    },
    {
        "scheme_code": "HKPFS",
        "scheme_name": "Hong Kong PhD Fellowship Scheme",
        "path": "funding/hkpfs/hkpfs.html",
        "description": "Attracts top international research postgraduate students to pursue PhD programmes in HK.",
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


def _extract_deadlines_from_html(html: str, scheme: dict[str, str]) -> list[dict[str, Any]]:
    soup = BeautifulSoup(html, "html.parser")
    results: list[dict[str, Any]] = []
    text = soup.get_text(" ", strip=True)

    deadline_patterns = [
        re.compile(r"deadline[:\s]*(\d{1,2}\s+\w+\s+\d{4})", re.IGNORECASE),
        re.compile(r"closing\s+date[:\s]*(\d{1,2}\s+\w+\s+\d{4})", re.IGNORECASE),
        re.compile(r"submit(?:ted)?\s+(?:by|before)[:\s]*(\d{1,2}\s+\w+\s+\d{4})", re.IGNORECASE),
        re.compile(r"(\d{1,2}\s+(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4})", re.IGNORECASE),
    ]

    seen_dates: set[str] = set()
    for pattern in deadline_patterns:
        for match in pattern.finditer(text):
            parsed = _parse_date(match.group(1) if pattern.groups else match.group(0))
            if parsed and parsed not in seen_dates:
                seen_dates.add(parsed)
                results.append({
                    "scheme_name": scheme["scheme_name"],
                    "scheme_code": scheme["scheme_code"],
                    "deadline_date": parsed,
                    "call_url": RGC_BASE_URL + scheme["path"],
                    "description": scheme["description"],
                })

    return results


def scrape_rgc_deadlines() -> list[dict]:
    """Fetch grant deadlines from the RGC website.

    Scrapes each known RGC scheme page for deadline dates.
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
            for scheme in KNOWN_SCHEMES:
                url = RGC_BASE_URL + scheme["path"]
                try:
                    resp = client.get(url)
                    resp.raise_for_status()
                    deadlines = _extract_deadlines_from_html(resp.text, scheme)
                    all_deadlines.extend(deadlines)
                    logger.info(
                        "RGC %s: found %d deadline(s) from %s",
                        scheme["scheme_code"], len(deadlines), url,
                    )
                except httpx.HTTPError as exc:
                    logger.warning("RGC %s: failed to fetch %s – %s", scheme["scheme_code"], url, exc)
                    all_deadlines.append({
                        "scheme_name": scheme["scheme_name"],
                        "scheme_code": scheme["scheme_code"],
                        "deadline_date": None,
                        "call_url": url,
                        "description": scheme["description"],
                    })

    except httpx.HTTPError as exc:
        logger.error("RGC scraper transport error: %s", exc)

    if not all_deadlines:
        logger.info("RGC scraper: no live deadlines found, returning scheme metadata")
        for scheme in KNOWN_SCHEMES:
            all_deadlines.append({
                "scheme_name": scheme["scheme_name"],
                "scheme_code": scheme["scheme_code"],
                "deadline_date": None,
                "call_url": RGC_BASE_URL + scheme["path"],
                "description": scheme["description"],
            })

    return all_deadlines
