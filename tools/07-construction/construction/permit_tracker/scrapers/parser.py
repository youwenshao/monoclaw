"""HTML parsing utilities for Buildings Department portal responses."""

from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger("openclaw.construction.permit_tracker.scrapers.parser")

BD_REFERENCE_PATTERN = re.compile(
    r"(BP|MW|OP|DM|NW|SC|FD)/(\d{4})/(\d{3,6})",
    re.IGNORECASE,
)

STATUS_NORMALIZATION: dict[str, str] = {
    "received": "Received",
    "under processing": "Under Processing",
    "processing": "Under Processing",
    "being processed": "Under Processing",
    "under examination": "Under Examination",
    "examination": "Under Examination",
    "approved": "Approved",
    "approval granted": "Approved",
    "consent issued": "Consent Issued",
    "consent to commence": "Consent Issued",
    "consent granted": "Consent Issued",
    "rejected": "Rejected",
    "returned": "Returned",
    "returned for amendment": "Returned for Amendment",
    "amendment required": "Returned for Amendment",
    "withdrawn": "Withdrawn",
    "occupation permit issued": "Occupation Permit Issued",
    "op issued": "Occupation Permit Issued",
    "pending": "Pending",
    "pending review": "Pending Review",
    "query raised": "Query Raised",
    "queries raised": "Query Raised",
    "site inspection": "Site Inspection",
    "completed": "Completed",
}


def parse_bd_status_page(html: str) -> dict[str, Any]:
    """Extract submission status data from a BD portal HTML response.

    Returns a dict with keys:
        reference, status, status_date, details, raw_html, stages.
    """
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        logger.warning("beautifulsoup4 not installed — cannot parse BD HTML")
        return {
            "reference": None,
            "status": "Unknown",
            "status_date": None,
            "details": "HTML parser unavailable",
            "raw_html": html[:500] if html else None,
            "stages": [],
        }

    soup = BeautifulSoup(html, "html.parser")

    reference = _extract_reference_from_soup(soup)
    status = "Unknown"
    status_date = None
    details = ""
    stages: list[dict[str, str]] = []

    status_table = (
        soup.find("table", class_=re.compile(r"status|result", re.I))
        or soup.find("table", id=re.compile(r"status|result", re.I))
        or _find_status_table(soup)
    )

    if status_table:
        rows = status_table.find_all("tr")
        for row in rows:
            cells = row.find_all(["td", "th"])
            if len(cells) < 2:
                continue

            label = cells[0].get_text(strip=True).lower()
            value = cells[1].get_text(strip=True)

            if any(k in label for k in ("status", "result", "decision")):
                status = parse_status_label(value)
            elif any(k in label for k in ("date", "effective")):
                status_date = value
            elif "reference" in label or "ref" in label:
                if not reference:
                    reference = value
            elif any(k in label for k in ("remark", "detail", "note")):
                details = value

    timeline_section = soup.find(
        "div", class_=re.compile(r"timeline|progress|stage", re.I)
    ) or soup.find("ol", class_=re.compile(r"timeline|progress", re.I))

    if timeline_section:
        for item in timeline_section.find_all("li"):
            stage_text = item.get_text(strip=True)
            stage_class = " ".join(item.get("class", []))
            is_current = "active" in stage_class or "current" in stage_class
            stages.append({
                "label": stage_text,
                "current": is_current,
            })

    if status == "Unknown" and not status_table:
        body_text = soup.get_text(separator=" ", strip=True)
        for raw_label, normalized in STATUS_NORMALIZATION.items():
            if raw_label in body_text.lower():
                status = normalized
                break

    return {
        "reference": reference,
        "status": status,
        "status_date": status_date,
        "details": details,
        "raw_html": html[:2000] if html else None,
        "stages": stages,
    }


def extract_bd_reference(text: str) -> str | None:
    """Extract a BD reference number from free text.

    Matches formats like BP/2024/1234, MW/2024/5678, etc.
    Returns the first match or None.
    """
    match = BD_REFERENCE_PATTERN.search(text)
    if match:
        return match.group(0).upper()
    return None


def parse_status_label(raw: str) -> str:
    """Normalize a raw BD status string to a canonical label."""
    if not raw:
        return "Unknown"
    cleaned = raw.strip()
    normalized = STATUS_NORMALIZATION.get(cleaned.lower())
    if normalized:
        return normalized
    for key, value in STATUS_NORMALIZATION.items():
        if key in cleaned.lower():
            return value
    return cleaned


def _extract_reference_from_soup(soup: Any) -> str | None:
    """Try to find a BD reference number anywhere in the page."""
    full_text = soup.get_text(separator=" ")
    return extract_bd_reference(full_text)


def _find_status_table(soup: Any) -> Any | None:
    """Heuristic search for the status table when no class/id matches."""
    for table in soup.find_all("table"):
        text = table.get_text(separator=" ", strip=True).lower()
        if any(kw in text for kw in ("status", "result", "application", "reference")):
            return table
    return None
