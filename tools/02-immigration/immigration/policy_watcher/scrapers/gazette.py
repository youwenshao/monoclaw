"""Government Gazette scraper for Cap. 115 Immigration Ordinance notices."""

from __future__ import annotations

import asyncio
import hashlib
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx
from bs4 import BeautifulSoup

from openclaw_shared.database import get_db

logger = logging.getLogger("openclaw.immigration.policy_watcher.scrapers.gazette")

USER_AGENT = "MonoClaw PolicyWatcher/1.0"
BASE_URL = "https://www.gld.gov.hk/egazette/"
SEARCH_URL = f"{BASE_URL}english/gazette/toc.php"
REQUEST_DELAY = 3.0
MAX_RETRIES = 3
INITIAL_BACKOFF = 2.0

_LN_PATTERN = re.compile(r"L\.?\s*N\.?\s*(\d+)\s*(?:of\s*)?(\d{4})?", re.IGNORECASE)
_GN_PATTERN = re.compile(r"G\.?\s*N\.?\s*(\d+)\s*(?:of\s*)?(\d{4})?", re.IGNORECASE)
_GAZ_REF_PATTERN = re.compile(
    r"(?:Vol|Volume)\s*\.?\s*(\d+)\s*No\s*\.?\s*(\d+)", re.IGNORECASE
)

CAP115_KEYWORDS = [
    "immigration ordinance",
    "cap. 115",
    "cap 115",
    "immigration (amendment)",
    "immigration rules",
    "entry permit",
    "limit of stay",
    "conditions of stay",
]


async def _fetch_with_retry(
    client: httpx.AsyncClient,
    url: str,
    *,
    params: dict | None = None,
) -> httpx.Response | None:
    for attempt in range(MAX_RETRIES):
        try:
            resp = await client.get(url, params=params, timeout=30)
            resp.raise_for_status()
            return resp
        except (httpx.HTTPStatusError, httpx.ConnectError, httpx.TimeoutException) as exc:
            wait = INITIAL_BACKOFF * (2 ** attempt)
            logger.warning(
                "Gazette fetch attempt %d/%d failed (%s), retrying in %.1fs",
                attempt + 1, MAX_RETRIES, exc, wait,
            )
            if attempt < MAX_RETRIES - 1:
                await asyncio.sleep(wait)
        except httpx.HTTPError as exc:
            logger.error("Gazette fetch unrecoverable error: %s", exc)
            return None
    logger.error("Gazette fetch exhausted retries for %s", url)
    return None


def _is_cap115_related(text: str) -> bool:
    lower = text.lower()
    return any(kw in lower for kw in CAP115_KEYWORDS)


def _extract_identifiers(text: str) -> dict[str, str | None]:
    ln_match = _LN_PATTERN.search(text)
    gn_match = _GN_PATTERN.search(text)
    gaz_match = _GAZ_REF_PATTERN.search(text)
    return {
        "ln_number": f"L.N. {ln_match.group(1)}" if ln_match else None,
        "ln_year": ln_match.group(2) if ln_match and ln_match.group(2) else None,
        "gn_number": f"G.N. {gn_match.group(1)}" if gn_match else None,
        "gn_year": gn_match.group(2) if gn_match and gn_match.group(2) else None,
        "gazette_ref": (
            f"Vol. {gaz_match.group(1)} No. {gaz_match.group(2)}" if gaz_match else None
        ),
    }


def _parse_gazette_page(html: str, base_url: str) -> list[dict[str, Any]]:
    soup = BeautifulSoup(html, "lxml")
    results: list[dict[str, Any]] = []

    for section_heading in ("Legal Notices", "Government Notices"):
        section = soup.find(string=re.compile(section_heading, re.IGNORECASE))
        if not section:
            continue
        container = section.find_parent("table") or section.find_parent("div")
        if not container:
            continue

        for row in container.find_all("tr"):
            cells = row.find_all("td")
            if len(cells) < 2:
                continue

            title_cell = cells[1] if len(cells) > 1 else cells[0]
            title_text = title_cell.get_text(strip=True)
            if not _is_cap115_related(title_text):
                continue

            link = title_cell.find("a", href=True)
            doc_url = ""
            if link:
                href = link["href"]
                doc_url = href if href.startswith("http") else f"{base_url.rstrip('/')}/{href.lstrip('/')}"

            ids = _extract_identifiers(title_text)
            gazette_ref = ids["gazette_ref"]
            if ids["ln_number"]:
                gazette_ref = gazette_ref or ids["ln_number"]
            elif ids["gn_number"]:
                gazette_ref = gazette_ref or ids["gn_number"]

            date_cell = cells[0] if len(cells) > 1 else None
            pub_date = None
            if date_cell:
                date_text = date_cell.get_text(strip=True)
                for fmt in ("%d/%m/%Y", "%d.%m.%Y", "%Y-%m-%d", "%d %B %Y"):
                    try:
                        pub_date = datetime.strptime(date_text, fmt).date().isoformat()
                        break
                    except ValueError:
                        continue

            results.append({
                "title": title_text,
                "document_url": doc_url,
                "gazette_ref": gazette_ref,
                "published_date": pub_date,
                "section_type": section_heading,
            })

    return results


def _store_documents(
    db_path: str | Path,
    source_id: int,
    documents: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    new_docs: list[dict[str, Any]] = []
    with get_db(db_path) as conn:
        for doc in documents:
            existing = conn.execute(
                "SELECT id FROM policy_documents WHERE document_url = ? AND title = ?",
                (doc["document_url"], doc["title"]),
            ).fetchone()
            if existing:
                continue

            content_text = doc.get("content_text", doc["title"])
            content_hash = hashlib.sha256(content_text.encode()).hexdigest()

            cursor = conn.execute(
                """INSERT INTO policy_documents
                   (source_id, title, document_url, content_text, content_hash,
                    gazette_ref, published_date)
                   VALUES (?,?,?,?,?,?,?)""",
                (
                    source_id,
                    doc["title"],
                    doc["document_url"],
                    content_text,
                    content_hash,
                    doc.get("gazette_ref"),
                    doc.get("published_date"),
                ),
            )
            doc["id"] = cursor.lastrowid
            doc["content_hash"] = content_hash
            new_docs.append(doc)

        if new_docs:
            conn.execute(
                "UPDATE policy_sources SET last_scraped = ? WHERE id = ?",
                (datetime.utcnow().isoformat(), source_id),
            )

    return new_docs


async def scrape_gazette(db_path: str | Path, config: dict) -> list[dict]:
    """Scrape gazette.gov.hk for immigration-related Legal Notices and Government Notices."""
    logger.info("Starting Government Gazette scrape")

    with get_db(db_path) as conn:
        source = conn.execute(
            "SELECT * FROM policy_sources WHERE source_name = 'Government Gazette'"
        ).fetchone()

    if not source:
        logger.warning("No Gazette source configured in policy_sources")
        return []

    source_data = dict(source)
    all_docs: list[dict[str, Any]] = []

    async with httpx.AsyncClient(
        headers={"User-Agent": USER_AGENT},
        follow_redirects=True,
    ) as client:
        resp = await _fetch_with_retry(client, SEARCH_URL)
        if not resp:
            logger.error("Failed to fetch gazette index")
            return []

        documents = _parse_gazette_page(resp.text, BASE_URL)
        logger.info("Found %d Cap. 115 related gazette entries", len(documents))

        for doc in documents:
            if doc["document_url"]:
                await asyncio.sleep(REQUEST_DELAY)
                detail_resp = await _fetch_with_retry(client, doc["document_url"])
                if detail_resp:
                    detail_soup = BeautifulSoup(detail_resp.text, "lxml")
                    content_el = (
                        detail_soup.find("div", class_="gazette-content")
                        or detail_soup.find("div", id="content")
                        or detail_soup.find("body")
                    )
                    if content_el:
                        doc["content_text"] = content_el.get_text(separator="\n", strip=True)

            all_docs.append(doc)

    new_docs = _store_documents(db_path, source_data["id"], all_docs)
    logger.info("Stored %d new gazette documents", len(new_docs))
    return new_docs
