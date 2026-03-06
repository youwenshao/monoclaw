"""LegCo Panel on Security papers scraper."""

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

logger = logging.getLogger("openclaw.immigration.policy_watcher.scrapers.legco")

USER_AGENT = "MonoClaw PolicyWatcher/1.0"
BASE_URL = "https://www.legco.gov.hk"
PANEL_URL = f"{BASE_URL}/en/committees/panel/se.html"
REQUEST_DELAY = 3.0
MAX_RETRIES = 3
INITIAL_BACKOFF = 2.0

IMMIGRATION_KEYWORDS = [
    "immigration", "admission scheme", "talent", "employment",
    "visa", "quality migrant", "IANG", "GEP", "ASMTP",
    "QMAS", "TTPS", "top talent", "new arrivals",
    "cap. 115", "cap 115", "entry permit", "dependant",
]


async def _fetch_with_retry(
    client: httpx.AsyncClient,
    url: str,
) -> httpx.Response | None:
    for attempt in range(MAX_RETRIES):
        try:
            resp = await client.get(url, timeout=30)
            resp.raise_for_status()
            return resp
        except (httpx.HTTPStatusError, httpx.ConnectError, httpx.TimeoutException) as exc:
            wait = INITIAL_BACKOFF * (2 ** attempt)
            logger.warning(
                "LegCo fetch attempt %d/%d failed (%s), retrying in %.1fs",
                attempt + 1, MAX_RETRIES, exc, wait,
            )
            if attempt < MAX_RETRIES - 1:
                await asyncio.sleep(wait)
        except httpx.HTTPError as exc:
            logger.error("LegCo fetch unrecoverable error: %s", exc)
            return None
    logger.error("LegCo fetch exhausted retries for %s", url)
    return None


def _is_immigration_related(text: str) -> bool:
    lower = text.lower()
    return any(kw in lower for kw in IMMIGRATION_KEYWORDS)


def _parse_panel_page(html: str) -> list[dict[str, Any]]:
    soup = BeautifulSoup(html, "lxml")
    results: list[dict[str, Any]] = []

    for table in soup.find_all("table"):
        for row in table.find_all("tr"):
            cells = row.find_all("td")
            if len(cells) < 2:
                continue

            full_text = row.get_text(strip=True)
            if not _is_immigration_related(full_text):
                continue

            date_text = cells[0].get_text(strip=True)
            pub_date = None
            date_match = re.search(r"(\d{1,2})[./\-](\d{1,2})[./\-](\d{4})", date_text)
            if date_match:
                try:
                    d, m, y = date_match.groups()
                    pub_date = datetime(int(y), int(m), int(d)).date().isoformat()
                except ValueError:
                    pass

            title_cell = cells[-1]
            title = title_cell.get_text(strip=True)[:300]

            links: list[dict[str, str]] = []
            for a in title_cell.find_all("a", href=True):
                href = a["href"]
                if href.startswith("http"):
                    url = href
                elif href.startswith("/"):
                    url = f"{BASE_URL}{href}"
                else:
                    url = f"{BASE_URL}/en/committees/panel/{href}"
                links.append({"text": a.get_text(strip=True), "url": url})

            doc_url = links[0]["url"] if links else ""

            results.append({
                "title": title,
                "published_date": pub_date,
                "document_url": doc_url,
                "paper_links": links,
            })

    if not results:
        for li in soup.find_all("li"):
            text = li.get_text(strip=True)
            if not _is_immigration_related(text):
                continue
            link = li.find("a", href=True)
            url = ""
            if link:
                href = link["href"]
                url = href if href.startswith("http") else f"{BASE_URL}{href}"
            results.append({
                "title": text[:300],
                "published_date": None,
                "document_url": url,
                "paper_links": [],
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

            content_text = doc.get("content_text") or doc["title"]
            content_hash = hashlib.sha256(content_text.encode()).hexdigest()

            cursor = conn.execute(
                """INSERT INTO policy_documents
                   (source_id, title, document_url, content_text, content_hash, published_date)
                   VALUES (?,?,?,?,?,?)""",
                (
                    source_id,
                    doc["title"],
                    doc["document_url"],
                    content_text,
                    content_hash,
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


async def scrape_legco(db_path: str | Path, config: dict) -> list[dict]:
    """Scrape LegCo Panel on Security papers for immigration-related items."""
    logger.info("Starting LegCo Panel on Security scrape")

    with get_db(db_path) as conn:
        source = conn.execute(
            "SELECT * FROM policy_sources WHERE source_name = 'LegCo Panel on Security'"
        ).fetchone()

    if not source:
        logger.warning("No LegCo source configured in policy_sources")
        return []

    source_data = dict(source)

    async with httpx.AsyncClient(
        headers={"User-Agent": USER_AGENT},
        follow_redirects=True,
    ) as client:
        resp = await _fetch_with_retry(client, PANEL_URL)
        if not resp:
            logger.error("Failed to fetch LegCo panel page")
            return []

        entries = _parse_panel_page(resp.text)
        logger.info("Found %d immigration-related LegCo papers", len(entries))

        for entry in entries:
            if entry["document_url"] and entry["document_url"].endswith(".htm"):
                await asyncio.sleep(REQUEST_DELAY)
                detail_resp = await _fetch_with_retry(client, entry["document_url"])
                if detail_resp:
                    detail_soup = BeautifulSoup(detail_resp.text, "lxml")
                    body = detail_soup.find("body")
                    if body:
                        entry["content_text"] = body.get_text(separator="\n", strip=True)[:10000]

    new_docs = _store_documents(db_path, source_data["id"], entries)
    logger.info("Stored %d new LegCo documents", len(new_docs))
    return new_docs
