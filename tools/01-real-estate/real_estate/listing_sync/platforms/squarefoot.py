"""Playwright-based adapter for Squarefoot (squarefoot.com.hk).

Squarefoot is an English-first Hong Kong property portal.
Constraints: max 30 photos, recommended image size 1200×900.
"""

from __future__ import annotations

import logging
from pathlib import Path

from real_estate.listing_sync.platforms.base import PlatformAdapter

logger = logging.getLogger("listing_sync.platforms.squarefoot")


class SquarefootAdapter(PlatformAdapter):
    PLATFORM_NAME = "squarefoot"
    MAX_PHOTOS = 30
    IMAGE_SPEC = (1200, 900)

    BASE_URL = "https://www.squarefoot.com.hk"
    LOGIN_URL = f"{BASE_URL}/agent/login"
    POST_URL = f"{BASE_URL}/agent/listing/create"

    def __init__(self, username: str, password: str, user_data_dir: str | Path | None = None) -> None:
        self._username = username
        self._password = password
        self._user_data_dir = str(user_data_dir) if user_data_dir else None
        self._browser = None
        self._context = None

    async def _ensure_browser(self):
        if self._context is not None:
            return

        from playwright.async_api import async_playwright

        pw = await async_playwright().start()
        if self._user_data_dir:
            self._context = await pw.chromium.launch_persistent_context(
                self._user_data_dir,
                headless=True,
                locale="en-HK",
                viewport={"width": 1280, "height": 800},
            )
        else:
            self._browser = await pw.chromium.launch(headless=True)
            self._context = await self._browser.new_context(
                locale="en-HK",
                viewport={"width": 1280, "height": 800},
            )

    async def _login(self):
        await self._ensure_browser()
        page = await self._context.new_page()
        try:
            await page.goto(self.LOGIN_URL, wait_until="networkidle")
            if await page.query_selector("input[name='email']"):
                await page.fill("input[name='email']", self._username)
                await page.fill("input[name='password']", self._password)
                await page.click("button[type='submit']")
                await page.wait_for_load_state("networkidle")
                logger.info("Logged into Squarefoot as %s", self._username)
            else:
                logger.info("Already logged into Squarefoot")
        finally:
            await page.close()

    def _build_form_data(self, listing: dict) -> dict:
        """Map our canonical listing dict to Squarefoot's English-first form fields."""
        return {
            "title": listing.get("title_en") or listing.get("title_zh", ""),
            "description": listing.get("description_adapted", listing.get("description_master", "")),
            "district": listing.get("district", ""),
            "estate_name": listing.get("estate", ""),
            "address": listing.get("address", ""),
            "saleable_area": str(listing.get("saleable_area_sqft", "")),
            "gross_area": str(listing.get("gross_area_sqft", "")),
            "asking_price": str(listing.get("price_hkd", "")),
            "bedrooms": str(listing.get("bedrooms", "")),
            "bathrooms": str(listing.get("bathrooms", "")),
            "floor_level": listing.get("floor", ""),
            "facing": listing.get("facing", ""),
        }

    async def post_listing(self, listing: dict, images: list[str]) -> str:
        await self._login()
        page = await self._context.new_page()
        try:
            await page.goto(self.POST_URL, wait_until="networkidle")
            form = self._build_form_data(listing)

            for field_name, value in form.items():
                selector = f"[name='{field_name}'], #{field_name}"
                el = await page.query_selector(selector)
                if el and value:
                    await el.fill(value)

            capped = images[: self.MAX_PHOTOS]
            file_input = await page.query_selector("input[type='file']")
            if file_input and capped:
                await file_input.set_input_files(capped)

            await page.click("button[type='submit']")
            await page.wait_for_load_state("networkidle")

            platform_id = page.url.split("/")[-1] or "pending"
            logger.info("Posted listing to Squarefoot: %s", platform_id)
            return platform_id
        finally:
            await page.close()

    async def update_listing(self, platform_id: str, listing: dict) -> bool:
        await self._login()
        page = await self._context.new_page()
        try:
            edit_url = f"{self.BASE_URL}/agent/listing/{platform_id}/edit"
            await page.goto(edit_url, wait_until="networkidle")
            form = self._build_form_data(listing)

            for field_name, value in form.items():
                selector = f"[name='{field_name}'], #{field_name}"
                el = await page.query_selector(selector)
                if el and value:
                    await el.fill(value)

            await page.click("button[type='submit']")
            await page.wait_for_load_state("networkidle")
            logger.info("Updated listing %s on Squarefoot", platform_id)
            return True
        except Exception:
            logger.exception("Failed to update listing %s on Squarefoot", platform_id)
            return False
        finally:
            await page.close()

    async def remove_listing(self, platform_id: str) -> bool:
        await self._login()
        page = await self._context.new_page()
        try:
            delete_url = f"{self.BASE_URL}/agent/listing/{platform_id}/delete"
            await page.goto(delete_url, wait_until="networkidle")
            confirm = await page.query_selector("button.confirm, [data-action='delete']")
            if confirm:
                await confirm.click()
                await page.wait_for_load_state("networkidle")
            logger.info("Removed listing %s from Squarefoot", platform_id)
            return True
        except Exception:
            logger.exception("Failed to remove listing %s from Squarefoot", platform_id)
            return False
        finally:
            await page.close()

    async def get_stats(self, platform_id: str) -> dict:
        await self._login()
        page = await self._context.new_page()
        try:
            stats_url = f"{self.BASE_URL}/agent/listing/{platform_id}/stats"
            await page.goto(stats_url, wait_until="networkidle")

            views_el = await page.query_selector(".stat-views, [data-stat='views']")
            inquiries_el = await page.query_selector(".stat-inquiries, [data-stat='inquiries']")

            views = int(await views_el.inner_text()) if views_el else 0
            inquiries = int(await inquiries_el.inner_text()) if inquiries_el else 0
            return {"platform": self.PLATFORM_NAME, "platform_id": platform_id, "views": views, "inquiries": inquiries}
        except Exception:
            logger.exception("Failed to fetch stats for %s on Squarefoot", platform_id)
            return {"platform": self.PLATFORM_NAME, "platform_id": platform_id, "views": 0, "inquiries": 0}
        finally:
            await page.close()

    async def close(self):
        if self._context:
            await self._context.close()
            self._context = None
        if self._browser:
            await self._browser.close()
            self._browser = None
