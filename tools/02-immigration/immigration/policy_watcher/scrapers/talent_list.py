"""Talent List (talentlist.gov.hk) update checker."""

from __future__ import annotations

import asyncio
import hashlib
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx
from bs4 import BeautifulSoup

from openclaw_shared.database import get_db

logger = logging.getLogger("openclaw.immigration.policy_watcher.scrapers.talent_list")

USER_AGENT = "MonoClaw PolicyWatcher/1.0"
BASE_URL = "https://www.talentlist.gov.hk"
TALENT_LIST_EN = f"{BASE_URL}/en/"
REQUEST_DELAY = 3.0
MAX_RETRIES = 3
INITIAL_BACKOFF = 2.0


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
                "TalentList fetch attempt %d/%d failed (%s), retrying in %.1fs",
                attempt + 1, MAX_RETRIES, exc, wait,
            )
            if attempt < MAX_RETRIES - 1:
                await asyncio.sleep(wait)
        except httpx.HTTPError as exc:
            logger.error("TalentList fetch unrecoverable error: %s", exc)
            return None
    logger.error("TalentList fetch exhausted retries for %s", url)
    return None


def _extract_talent_professions(soup: BeautifulSoup) -> list[dict[str, str]]:
    """Extract the list of talent professions from the page."""
    professions: list[dict[str, str]] = []
    for section in soup.find_all(["div", "section"], class_=lambda c: c and "profession" in str(c).lower()):
        title = section.find(["h2", "h3", "h4"])
        desc = section.find("p")
        professions.append({
            "title": title.get_text(strip=True) if title else "",
            "description": desc.get_text(strip=True) if desc else "",
        })

    if not professions:
        for li in soup.find_all("li"):
            text = li.get_text(strip=True)
            if len(text) > 10:
                professions.append({"title": text[:200], "description": ""})

    return professions


def _build_content_snapshot(soup: BeautifulSoup) -> str:
    """Build a text snapshot of the talent list page for change detection."""
    main = (
        soup.find("main")
        or soup.find("div", id="content")
        or soup.find("div", class_="content")
        or soup.find("body")
    )
    if not main:
        return ""
    return main.get_text(separator="\n", strip=True)


async def scrape_talent_list(db_path: str | Path, config: dict) -> list[dict]:
    """Check talentlist.gov.hk for updates to the Hong Kong Talent List."""
    logger.info("Starting Talent List update check")

    with get_db(db_path) as conn:
        source = conn.execute(
            "SELECT * FROM policy_sources WHERE source_name = 'Talent List'"
        ).fetchone()

    if not source:
        logger.warning("No Talent List source configured in policy_sources")
        return []

    source_data = dict(source)

    async with httpx.AsyncClient(
        headers={"User-Agent": USER_AGENT},
        follow_redirects=True,
    ) as client:
        resp = await _fetch_with_retry(client, TALENT_LIST_EN)
        if not resp:
            logger.error("Failed to fetch Talent List page")
            return []

        soup = BeautifulSoup(resp.text, "lxml")
        content_text = _build_content_snapshot(soup)
        if not content_text:
            logger.warning("No content extracted from Talent List page")
            return []

        content_hash = hashlib.sha256(content_text.encode()).hexdigest()

        with get_db(db_path) as conn:
            prev = conn.execute(
                """SELECT id, content_hash FROM policy_documents
                   WHERE source_id = ?
                   ORDER BY scraped_at DESC LIMIT 1""",
                (source_data["id"],),
            ).fetchone()

        if prev and dict(prev)["content_hash"] == content_hash:
            logger.info("Talent List unchanged (hash match)")
            with get_db(db_path) as conn:
                conn.execute(
                    "UPDATE policy_sources SET last_scraped = ? WHERE id = ?",
                    (datetime.utcnow().isoformat(), source_data["id"]),
                )
            return []

        professions = _extract_talent_professions(soup)
        title = "Hong Kong Talent List"
        if professions:
            title += f" ({len(professions)} professions listed)"

        new_docs: list[dict[str, Any]] = []
        with get_db(db_path) as conn:
            cursor = conn.execute(
                """INSERT INTO policy_documents
                   (source_id, title, document_url, content_text, content_hash, published_date)
                   VALUES (?,?,?,?,?,?)""",
                (
                    source_data["id"],
                    title,
                    TALENT_LIST_EN,
                    content_text[:50000],
                    content_hash,
                    datetime.utcnow().date().isoformat(),
                ),
            )
            doc_id = cursor.lastrowid
            conn.execute(
                "UPDATE policy_sources SET last_scraped = ? WHERE id = ?",
                (datetime.utcnow().isoformat(), source_data["id"]),
            )

        new_docs.append({
            "id": doc_id,
            "title": title,
            "document_url": TALENT_LIST_EN,
            "content_hash": content_hash,
            "published_date": datetime.utcnow().date().isoformat(),
            "professions": professions,
            "previous_document_id": dict(prev)["id"] if prev else None,
        })

        if prev:
            logger.info("Talent List content changed — new snapshot stored")
        else:
            logger.info("Talent List first snapshot stored")

        return new_docs
