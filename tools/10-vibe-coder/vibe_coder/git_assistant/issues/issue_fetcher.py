"""Fetch open issues from the GitHub Issues API."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

import httpx


@dataclass
class Issue:
    number: int
    title: str
    body: str
    labels: list[str] = field(default_factory=list)
    author: str = ""
    created_at: str = ""


GITHUB_API = "https://api.github.com"


class IssueFetcher:
    """Retrieve open issues from a GitHub repository."""

    async def fetch_open_issues(
        self,
        owner: str,
        repo: str,
        token: str,
        *,
        per_page: int = 30,
        page: int = 1,
    ) -> list[Issue]:
        url = f"{GITHUB_API}/repos/{owner}/{repo}/issues"
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        params = {
            "state": "open",
            "per_page": per_page,
            "page": page,
        }

        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.get(url, headers=headers, params=params)
            resp.raise_for_status()
            data = resp.json()

        issues: list[Issue] = []
        for item in data:
            if item.get("pull_request"):
                continue
            issues.append(
                Issue(
                    number=item["number"],
                    title=item["title"],
                    body=item.get("body") or "",
                    labels=[lbl["name"] for lbl in item.get("labels", [])],
                    author=item.get("user", {}).get("login", ""),
                    created_at=item.get("created_at", ""),
                )
            )

        return issues
