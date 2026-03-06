"""Immigration Department (ImmD) press release and announcement scraper."""

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

logger = logging.getLogger("openclaw.immigration.policy_watcher.scrapers.immd")

USER_AGENT = "MonoClaw PolicyWatcher/1.0"
BASE_URL = "https://www.immd.gov.hk"
PRESS_URL = f"{BASE_URL}/eng/press/press.html"
ANNOUNCEMENTS_URL = f"{BASE_URL}/eng/useful_information/announcements.html"
REQUEST_DELAY = 3.0
MAX_RETRIES = 3
INITIAL_BACKOFF = 2.0

IMMIGRATION_KEYWORDS = [
    "employment", "visa", "permit", "talent", "admission",
    "immigration", "IANG", "GEP", "ASMTP", "QMAS", "TTPS",
    "top talent", "quality migrant", "dependant", "extension",
    "application", "policy", "scheme", "regulation",
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
                "ImmD fetch attempt %d/%d failed (%s), retrying in %.1fs",
                attempt + 1, MAX_RETRIES, exc, wait,
            )
            if attempt < MAX_RETRIES - 1:
                await asyncio.sleep(wait)
        except httpx.HTTPError as exc:
            logger.error("ImmD fetch unrecoverable error: %s", exc)
            return None
    logger.error("ImmD fetch exhausted retries for %s", url)
    return None


def _is_immigration_related(text: str) -> bool:
    lower = text.lower()
    return any(kw in lower for kw in IMMIGRATION_KEYWORDS)


def _parse_date(text: str) -> str | None:
    text = text.strip()
    for fmt in ("%d.%m.%Y", "%d/%m/%Y", "%Y-%m-%d", "%d %B %Y", "%B %d, %Y"):
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            continue
    date_match = re.search(r"(\d{1,2})[./\-](\d{1,2})[./\-](\d{4})", text)
    if date_match:
        try:
            d, m, y = date_match.groups()
            return datetime(int(y), int(m), int(d)).date().isoformat()
        except ValueError:
            pass
    return None


def _parse_press_list(html: str) -> list[dict[str, Any]]:
    soup = BeautifulSoup(html, "lxml")
    results: list[dict[str, Any]] = []

    for table in soup.find_all("table"):
        for row in table.find_all("tr"):
            cells = row.find_all("td")
            if len(cells) < 2:
                continue

            date_text = cells[0].get_text(strip=True)
            title_cell = cells[-1]
            title = title_cell.get_text(strip=True)

            if not _is_immigration_related(title):
                continue

            link = title_cell.find("a", href=True)
            url = ""
            if link:
                href = link["href"]
                if href.startswith("http"):
                    url = href
                elif href.startswith("/"):
                    url = f"{BASE_URL}{href}"
                else:
                    url = f"{BASE_URL}/eng/press/{href}"

            results.append({
                "title": title,
                "published_date": _parse_date(date_text),
                "document_url": url,
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
                "title": text[:200],
                "published_date": None,
                "document_url": url,
            })

    return results


async def _fetch_article_content(
    client: httpx.AsyncClient,
    url: str,
) -> str | None:
    if not url:
        return None
    resp = await _fetch_with_retry(client, url)
    if not resp:
        return None
    soup = BeautifulSoup(resp.text, "lxml")
    content = (
        soup.find("div", class_="pressrelease")
        or soup.find("div", id="pressrelease")
        or soup.find("div", class_="content")
        or soup.find("article")
        or soup.find("div", id="content")
    )
    if content:
        return content.get_text(separator="\n", strip=True)
    body = soup.find("body")
    return body.get_text(separator="\n", strip=True)[:5000] if body else None


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


async def scrape_immd(db_path: str | Path, config: dict) -> list[dict]:
    """Scrape immd.gov.hk press releases and announcements for policy changes."""
    logger.info("Starting ImmD press release scrape")

    with get_db(db_path) as conn:
        source = conn.execute(
            "SELECT * FROM policy_sources WHERE source_name = 'Immigration Department'"
        ).fetchone()

    if not source:
        logger.warning("No ImmD source configured in policy_sources")
        return []

    source_data = dict(source)
    all_docs: list[dict[str, Any]] = []

    async with httpx.AsyncClient(
        headers={"User-Agent": USER_AGENT},
        follow_redirects=True,
    ) as client:
        for page_url in (PRESS_URL, ANNOUNCEMENTS_URL):
            resp = await _fetch_with_retry(client, page_url)
            if not resp:
                continue

            entries = _parse_press_list(resp.text)
            logger.info("Found %d immigration-related entries from %s", len(entries), page_url)

            for entry in entries:
                await asyncio.sleep(REQUEST_DELAY)
                content = await _fetch_article_content(client, entry["document_url"])
                if content:
                    entry["content_text"] = content
                all_docs.append(entry)

    new_docs = _store_documents(db_path, source_data["id"], all_docs)
    logger.info("Stored %d new ImmD documents", len(new_docs))
    return new_docs
