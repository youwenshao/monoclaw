"""NSFC (National Natural Science Foundation of China) deadline tracking."""

from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import Any

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger("openclaw.academic.grant_tracker.monitoring.nsfc")

NSFC_BASE_URL: str = "https://www.nsfc.gov.cn"
NSFC_NOTICE_URL = f"{NSFC_BASE_URL}/english/site_1/index.html"
USER_AGENT = "MonoClaw GrantTracker/1.0"

HK_NSFC_JOINT_SCHEMES: list[dict[str, str]] = [
    {
        "scheme_code": "NSFC-RGC",
        "scheme_name": "NSFC/RGC Joint Research Scheme",
        "description": "Joint scheme between NSFC and RGC for collaborative research projects between Mainland and HK researchers.",
        "url": "https://www.ugc.edu.hk/eng/rgc/funding/nsfc/nsfc.html",
        "typical_deadline_month": "March",
    },
    {
        "scheme_code": "NSFC-CRF",
        "scheme_name": "NSFC/RGC Collaborative Research Fund",
        "description": "Supports collaborative research involving Mainland and HK investigators under CRF umbrella.",
        "url": "https://www.ugc.edu.hk/eng/rgc/funding/crf/crf.html",
        "typical_deadline_month": "January",
    },
    {
        "scheme_code": "NSFC-Young",
        "scheme_name": "NSFC Young Scientists Fund (HK & Macao)",
        "description": "Supports young scientists in HK and Macao under 35 for exploratory research.",
        "url": "https://www.nsfc.gov.cn/english/site_1/index.html",
        "typical_deadline_month": "March",
    },
    {
        "scheme_code": "NSFC-General",
        "scheme_name": "NSFC General Programme (HK & Macao)",
        "description": "General programme open to HK and Macao researchers for fundamental research.",
        "url": "https://www.nsfc.gov.cn/english/site_1/index.html",
        "typical_deadline_month": "March",
    },
    {
        "scheme_code": "NSFC-Key",
        "scheme_name": "NSFC Key Programme (HK & Macao)",
        "description": "Supports significant research projects from HK and Macao institutions.",
        "url": "https://www.nsfc.gov.cn/english/site_1/index.html",
        "typical_deadline_month": "March",
    },
    {
        "scheme_code": "NSFC-Excellent",
        "scheme_name": "NSFC Excellent Young Scientists Fund (HK & Macao)",
        "description": "Supports outstanding young scientists in HK and Macao to carry out basic research.",
        "url": "https://www.nsfc.gov.cn/english/site_1/index.html",
        "typical_deadline_month": "April",
    },
]


def _parse_date(text: str) -> str | None:
    text = text.strip()
    for fmt in ("%Y-%m-%d", "%d %B %Y", "%B %d, %Y", "%Y年%m月%d日", "%d/%m/%Y"):
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            continue
    match = re.search(r"(\d{4})[./\-](\d{1,2})[./\-](\d{1,2})", text)
    if match:
        try:
            y, m, d = match.groups()
            return datetime(int(y), int(m), int(d)).date().isoformat()
        except ValueError:
            pass
    return None


def _extract_deadlines_from_html(html: str) -> list[dict[str, Any]]:
    soup = BeautifulSoup(html, "html.parser")
    results: list[dict[str, Any]] = []
    text = soup.get_text(" ", strip=True)

    hk_patterns = [
        re.compile(r"(Hong\s+Kong|Macao|港澳)", re.IGNORECASE),
    ]
    is_hk_relevant = any(p.search(text) for p in hk_patterns)
    if not is_hk_relevant:
        return results

    deadline_patterns = [
        re.compile(r"deadline[:\s]*(\d{4}[./\-]\d{1,2}[./\-]\d{1,2})", re.IGNORECASE),
        re.compile(r"closing\s+date[:\s]*(\d{4}[./\-]\d{1,2}[./\-]\d{1,2})", re.IGNORECASE),
        re.compile(r"(\d{1,2}\s+(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4})", re.IGNORECASE),
    ]

    for pattern in deadline_patterns:
        for match in pattern.finditer(text):
            raw = match.group(1) if match.lastindex else match.group(0)
            parsed = _parse_date(raw)
            if parsed:
                results.append({
                    "scheme_name": "NSFC Programme",
                    "scheme_code": "NSFC",
                    "deadline_date": parsed,
                    "call_url": NSFC_NOTICE_URL,
                    "description": "NSFC funding opportunity relevant to Hong Kong researchers.",
                })

    return results


def scrape_nsfc_deadlines() -> list[dict]:
    """Fetch NSFC deadlines relevant to Hong Kong researchers.

    Scrapes the NSFC English portal for HK/Macao-relevant notices.
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
            try:
                resp = client.get(NSFC_NOTICE_URL)
                resp.raise_for_status()
                deadlines = _extract_deadlines_from_html(resp.text)
                all_deadlines.extend(deadlines)
                logger.info("NSFC: found %d deadline(s) from main page", len(deadlines))
            except httpx.HTTPError as exc:
                logger.warning("NSFC: failed to fetch %s – %s", NSFC_NOTICE_URL, exc)

            rgc_nsfc_url = "https://www.ugc.edu.hk/eng/rgc/funding/nsfc/nsfc.html"
            try:
                resp = client.get(rgc_nsfc_url)
                resp.raise_for_status()
                soup = BeautifulSoup(resp.text, "html.parser")
                text = soup.get_text(" ", strip=True)

                date_pattern = re.compile(
                    r"(\d{1,2}\s+(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4})",
                    re.IGNORECASE,
                )
                for match in date_pattern.finditer(text):
                    parsed = _parse_date(match.group(0))
                    if parsed:
                        all_deadlines.append({
                            "scheme_name": "NSFC/RGC Joint Research Scheme",
                            "scheme_code": "NSFC-RGC",
                            "deadline_date": parsed,
                            "call_url": rgc_nsfc_url,
                            "description": "Joint scheme between NSFC and RGC.",
                        })
                logger.info("NSFC-RGC: scraped RGC page for joint scheme deadlines")
            except httpx.HTTPError as exc:
                logger.warning("NSFC-RGC: failed to fetch RGC page – %s", exc)

    except httpx.HTTPError as exc:
        logger.error("NSFC scraper transport error: %s", exc)

    return all_deadlines


def get_nsfc_hk_joint_schemes() -> list[dict]:
    """Return the known HK-NSFC joint funding schemes with metadata."""
    return [
        {
            "scheme_name": s["scheme_name"],
            "scheme_code": s["scheme_code"],
            "deadline_date": None,
            "call_url": s["url"],
            "description": s["description"],
        }
        for s in HK_NSFC_JOINT_SCHEMES
    ]
