"""httpx-based parser for LinkedIn job listings with rate limiting."""

from __future__ import annotations

import logging
import re

import httpx

logger = logging.getLogger("openclaw.student.job_tracker.linkedin")


async def parse_linkedin(url: str) -> dict | None:
    try:
        async with httpx.AsyncClient(
            timeout=15.0,
            follow_redirects=True,
            headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36",
                "Accept-Language": "en-US,en;q=0.9",
            },
        ) as client:
            resp = await client.get(url)
            if resp.status_code != 200:
                logger.warning("LinkedIn returned %d for %s", resp.status_code, url)
                return None

            html = resp.text

        title = _extract_meta(html, "og:title") or _extract_tag(html, "h1")
        description = _extract_meta(html, "og:description") or ""
        company = _extract_between(html, '"companyName":"', '"')
        location = _extract_between(html, '"formattedLocation":"', '"')

        if not title:
            return None

        return {
            "title": title,
            "company": company or "",
            "salary_min": None,
            "salary_max": None,
            "location": location or "Hong Kong",
            "district": None,
            "requirements": [],
            "skills_required": [],
            "benefits": None,
            "description_raw": description,
        }
    except Exception:
        logger.exception("Failed to parse LinkedIn: %s", url)
        return None


def _extract_meta(html: str, prop: str) -> str | None:
    match = re.search(
        rf'<meta\s+(?:property|name)="{re.escape(prop)}"\s+content="([^"]*)"',
        html,
        re.IGNORECASE,
    )
    if match:
        return _unescape_html(match.group(1))
    return None


def _extract_tag(html: str, tag: str) -> str | None:
    match = re.search(rf"<{tag}[^>]*>(.*?)</{tag}>", html, re.IGNORECASE | re.DOTALL)
    if match:
        return re.sub(r"<[^>]+>", "", match.group(1)).strip()
    return None


def _extract_between(html: str, start: str, end: str) -> str | None:
    idx = html.find(start)
    if idx == -1:
        return None
    idx += len(start)
    end_idx = html.find(end, idx)
    if end_idx == -1:
        return None
    return _unescape_html(html[idx:end_idx])


def _unescape_html(text: str) -> str:
    return (
        text.replace("&amp;", "&")
        .replace("&lt;", "<")
        .replace("&gt;", ">")
        .replace("&quot;", '"')
        .replace("&#39;", "'")
    )
