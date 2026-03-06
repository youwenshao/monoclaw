"""Batch DOI verification — single and bulk DOI checking with rate limiting."""

from __future__ import annotations

import asyncio
from typing import Any

import httpx

_TIMEOUT = httpx.Timeout(15.0, connect=10.0)


async def check_doi(doi: str) -> dict[str, Any]:
    """Verify a single DOI and return resolution metadata.

    Returns: {valid: bool, doi: str, resolved_url: str | None, metadata: dict}
    """
    doi = doi.strip()
    result: dict[str, Any] = {
        "valid": False,
        "doi": doi,
        "resolved_url": None,
        "metadata": {},
    }

    url = f"https://doi.org/{doi}"
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT, follow_redirects=True) as client:
            resp = await client.head(url)
            if resp.status_code < 400:
                result["valid"] = True
                result["resolved_url"] = str(resp.url)
    except httpx.HTTPError:
        return result

    if result["valid"]:
        try:
            async with httpx.AsyncClient(
                timeout=_TIMEOUT,
                headers={"Accept": "application/vnd.citationstyles.csl+json"},
            ) as client:
                resp = await client.get(url)
                if resp.status_code == 200:
                    result["metadata"] = resp.json()
        except (httpx.HTTPError, ValueError):
            pass

    return result


async def batch_check_dois(dois: list[str], delay_ms: int = 100) -> list[dict[str, Any]]:
    """Batch verify a list of DOIs with rate limiting.

    Args:
        dois: List of DOI strings to check.
        delay_ms: Delay between requests in milliseconds to avoid rate limits.

    Returns:
        List of result dicts in the same order as the input.
    """
    results: list[dict[str, Any]] = []
    delay_s = delay_ms / 1000.0

    for i, doi in enumerate(dois):
        result = await check_doi(doi)
        results.append(result)
        if i < len(dois) - 1:
            await asyncio.sleep(delay_s)

    return results
