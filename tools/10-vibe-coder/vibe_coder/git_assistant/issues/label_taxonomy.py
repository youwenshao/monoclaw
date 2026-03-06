"""Fetch label taxonomy from a GitHub repository."""

from __future__ import annotations

import httpx

GITHUB_API = "https://api.github.com"


class LabelTaxonomy:
    """Retrieve existing labels from a GitHub repository."""

    async def fetch_labels(
        self,
        owner: str,
        repo: str,
        token: str,
        *,
        per_page: int = 100,
    ) -> list[str]:
        url = f"{GITHUB_API}/repos/{owner}/{repo}/labels"
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        params: dict[str, int] = {"per_page": per_page}

        labels: list[str] = []
        async with httpx.AsyncClient(timeout=15) as client:
            page = 1
            while True:
                params["page"] = page
                resp = await client.get(url, headers=headers, params=params)
                resp.raise_for_status()
                data = resp.json()
                if not data:
                    break
                labels.extend(item["name"] for item in data)
                if len(data) < per_page:
                    break
                page += 1

        return sorted(labels)
