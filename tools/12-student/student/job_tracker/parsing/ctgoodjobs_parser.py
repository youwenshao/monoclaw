"""Playwright scraper for CTgoodjobs job listings."""

from __future__ import annotations

import asyncio
import logging

logger = logging.getLogger("openclaw.student.job_tracker.ctgoodjobs")


async def parse_ctgoodjobs(url: str) -> dict | None:
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        logger.warning("playwright not installed, cannot scrape CTgoodjobs")
        return None

    try:
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.goto(url, wait_until="domcontentloaded", timeout=15000)
            await asyncio.sleep(3)

            title = await _text(page, "h1, .job-title, [class*='title']")
            company = await _text(page, ".company-name, [class*='company'], .employer")
            location = await _text(page, ".location, [class*='location'], .work-location")
            salary_text = await _text(page, ".salary, [class*='salary'], .compensation")
            description = await _text(page, ".job-description, .job-detail, [class*='description'], .detail-content")

            benefits_el = await page.query_selector(".benefits, [class*='benefit']")
            benefits = (await benefits_el.inner_text()).strip() if benefits_el else None

            requirements: list[str] = []
            req_items = await page.query_selector_all(".requirements li, .job-requirements li")
            for item in req_items:
                t = (await item.inner_text()).strip()
                if t:
                    requirements.append(t)

            await browser.close()

        salary_min, salary_max = _parse_salary(salary_text)

        return {
            "title": title or "",
            "company": company or "",
            "salary_min": salary_min,
            "salary_max": salary_max,
            "location": location or "Hong Kong",
            "district": None,
            "requirements": requirements,
            "skills_required": [],
            "benefits": benefits,
            "description_raw": description or "",
        }
    except Exception:
        logger.exception("Failed to scrape CTgoodjobs: %s", url)
        return None


async def _text(page, selector: str) -> str | None:
    el = await page.query_selector(selector)
    if el:
        return (await el.inner_text()).strip()
    return None


def _parse_salary(text: str | None) -> tuple[float | None, float | None]:
    if not text:
        return None, None
    import re
    numbers = re.findall(r"[\d,]+", text.replace(",", ""))
    nums = [float(n) for n in numbers if n]
    if len(nums) >= 2:
        return min(nums), max(nums)
    if len(nums) == 1:
        return nums[0], nums[0]
    return None, None
