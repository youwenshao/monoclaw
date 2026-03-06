"""Playwright-based headless Chromium automation for the BRAVO/BISNET portal."""

from __future__ import annotations

import asyncio
import hashlib
import logging
import random
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger("openclaw.construction.permit_tracker.scrapers.bd_portal")

BRAVO_LOGIN_URL = "https://bravo.bd.gov.hk/login"
BISNET_SEARCH_URL = "https://www.bd.gov.hk/en/resources/online-tools/bisnet/index.html"
MAX_RETRIES = 3
INITIAL_BACKOFF = 2.0


async def _random_delay(lo: float = 2.0, hi: float = 5.0) -> None:
    await asyncio.sleep(random.uniform(lo, hi))


class BDPortalScraper:
    """Automated scraper for the Buildings Department BRAVO/BISNET portal.

    Requires Playwright async API. Falls back to mock data when Playwright
    is not installed so the rest of the application remains functional.
    """

    def __init__(self, credentials: dict[str, str]) -> None:
        self.credentials = credentials
        self._browser: Any = None
        self._context: Any = None
        self._page: Any = None
        self._logged_in = False
        self._cache_dir: Path | None = None

    def set_cache_dir(self, path: Path) -> None:
        self._cache_dir = path
        self._cache_dir.mkdir(parents=True, exist_ok=True)

    async def login(self) -> bool:
        """Authenticate against the BRAVO AP portal."""
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            logger.warning(
                "Playwright not installed — BD portal scraping unavailable. "
                "Install with: pip install playwright && playwright install chromium"
            )
            return False

        username = self.credentials.get("username", "")
        password = self.credentials.get("password", "")
        if not username or not password:
            logger.warning("BD portal credentials not configured")
            return False

        try:
            pw = await async_playwright().start()
            self._browser = await pw.chromium.launch(headless=True)
            self._context = await self._browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
            )
            self._page = await self._context.new_page()

            await self._page.goto(BRAVO_LOGIN_URL, wait_until="networkidle")
            await _random_delay(1.0, 2.0)

            await self._page.fill('input[name="username"], #username', username)
            await self._page.fill('input[name="password"], #password', password)
            await self._page.click('button[type="submit"], input[type="submit"]')
            await self._page.wait_for_load_state("networkidle")

            if "login" in self._page.url.lower():
                logger.error("BD portal login failed — still on login page")
                return False

            self._logged_in = True
            logger.info("BD portal login successful")
            return True

        except Exception:
            logger.exception("BD portal login error")
            return False

    async def scrape_status(self, bd_reference: str) -> dict[str, Any]:
        """Fetch the current status for a BD submission reference.

        Returns a dict with keys: reference, status, status_date, details, raw_html.
        Uses retry logic with exponential backoff.
        """
        for attempt in range(MAX_RETRIES):
            try:
                return await self._do_scrape(bd_reference)
            except Exception as exc:
                wait = INITIAL_BACKOFF * (2 ** attempt)
                logger.warning(
                    "BD scrape attempt %d/%d for %s failed (%s), retrying in %.1fs",
                    attempt + 1, MAX_RETRIES, bd_reference, exc, wait,
                )
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(wait)

        logger.error("Exhausted retries scraping BD reference %s", bd_reference)
        return self._mock_status(bd_reference)

    async def _do_scrape(self, bd_reference: str) -> dict[str, Any]:
        if not self._logged_in or self._page is None:
            logger.info("Not logged in — returning mock status for %s", bd_reference)
            return self._mock_status(bd_reference)

        await _random_delay()

        await self._page.goto(BISNET_SEARCH_URL, wait_until="networkidle")
        await _random_delay(1.0, 2.0)

        ref_input = self._page.locator(
            'input[name="refNo"], input[name="reference"], #refNo'
        ).first
        await ref_input.fill(bd_reference)
        await self._page.click('button:has-text("Search"), input[value="Search"]')
        await self._page.wait_for_load_state("networkidle")
        await _random_delay(1.0, 3.0)

        html = await self._page.content()
        self._cache_html(bd_reference, html)

        from construction.permit_tracker.scrapers.parser import parse_bd_status_page
        return parse_bd_status_page(html)

    def _cache_html(self, reference: str, html: str) -> None:
        if not self._cache_dir:
            return
        safe_ref = reference.replace("/", "_")
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = self._cache_dir / f"{safe_ref}_{ts}.html"
        try:
            path.write_text(html, encoding="utf-8")
            logger.debug("Cached HTML for %s at %s", reference, path)
        except OSError:
            logger.warning("Failed to cache HTML for %s", reference)

    @staticmethod
    def _mock_status(bd_reference: str) -> dict[str, Any]:
        """Return placeholder data when live scraping is unavailable."""
        logger.debug("Returning mock status for %s", bd_reference)
        return {
            "reference": bd_reference,
            "status": "Unknown",
            "status_date": None,
            "details": "Live portal scraping unavailable — using mock data",
            "raw_html": None,
            "mock": True,
        }

    async def close(self) -> None:
        """Release browser resources."""
        try:
            if self._browser:
                await self._browser.close()
                self._browser = None
                self._page = None
                self._context = None
                self._logged_in = False
                logger.info("BD portal browser closed")
        except Exception:
            logger.exception("Error closing BD portal browser")
