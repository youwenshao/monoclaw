"""Generate a CHANGELOG from Git commit history using LLM categorisation."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from vibe_coder.docu_writer.analyzers.git_analyzer import CommitInfo

CONVENTIONAL_RE = re.compile(
    r"^(?P<type>feat|fix|docs|style|refactor|perf|test|build|ci|chore|revert)"
    r"(?:\((?P<scope>[^)]+)\))?!?:\s*(?P<desc>.+)",
    re.IGNORECASE,
)

CATEGORY_ORDER = [
    "Features",
    "Bug Fixes",
    "Performance",
    "Documentation",
    "Refactoring",
    "Tests",
    "Build & CI",
    "Other",
]

TYPE_CATEGORY: dict[str, str] = {
    "feat": "Features",
    "fix": "Bug Fixes",
    "perf": "Performance",
    "docs": "Documentation",
    "refactor": "Refactoring",
    "style": "Refactoring",
    "test": "Tests",
    "build": "Build & CI",
    "ci": "Build & CI",
    "chore": "Other",
    "revert": "Other",
}


@dataclass
class CategorisedCommit:
    category: str
    scope: str | None
    description: str
    commit_hash: str
    author: str


class ChangelogGenerator:
    """Group commits by category and produce a formatted changelog."""

    async def generate(
        self,
        commits: list[CommitInfo],
        llm,
        *,
        version: str | None = None,
    ) -> str:
        categorised = self._auto_categorise(commits)
        uncategorised = [c for c in commits if not self._is_conventional(c.message)]

        if uncategorised:
            llm_categories = await self._llm_categorise(uncategorised, llm)
            categorised.extend(llm_categories)

        return self._render(categorised, version)

    # ------------------------------------------------------------------

    def _auto_categorise(self, commits: list[CommitInfo]) -> list[CategorisedCommit]:
        results: list[CategorisedCommit] = []
        for c in commits:
            m = CONVENTIONAL_RE.match(c.message)
            if m:
                cat = TYPE_CATEGORY.get(m.group("type").lower(), "Other")
                results.append(
                    CategorisedCommit(
                        category=cat,
                        scope=m.group("scope"),
                        description=m.group("desc").strip(),
                        commit_hash=c.hash,
                        author=c.author,
                    )
                )
        return results

    @staticmethod
    def _is_conventional(msg: str) -> bool:
        return CONVENTIONAL_RE.match(msg) is not None

    async def _llm_categorise(
        self,
        commits: list[CommitInfo],
        llm,
    ) -> list[CategorisedCommit]:
        listing = "\n".join(f"- [{c.hash}] {c.message}" for c in commits[:40])
        prompt = (
            "Categorise each commit below into one of: "
            "Features, Bug Fixes, Performance, Documentation, Refactoring, Tests, Build & CI, Other.\n"
            "Format: hash | category | one-line description\n\n"
            f"{listing}"
        )
        raw = await llm.complete(prompt)
        return self._parse_llm_categories(raw, commits)

    @staticmethod
    def _parse_llm_categories(
        raw: str,
        commits: list[CommitInfo],
    ) -> list[CategorisedCommit]:
        commit_map = {c.hash: c for c in commits}
        results: list[CategorisedCommit] = []
        for line in raw.strip().splitlines():
            parts = [p.strip() for p in line.split("|")]
            if len(parts) < 3:
                continue
            h = parts[0].strip("[] ")
            cat = parts[1]
            desc = parts[2]
            if cat not in CATEGORY_ORDER:
                cat = "Other"
            author = commit_map[h].author if h in commit_map else "unknown"
            results.append(
                CategorisedCommit(
                    category=cat,
                    scope=None,
                    description=desc,
                    commit_hash=h,
                    author=author,
                )
            )
        return results

    def _render(
        self,
        items: list[CategorisedCommit],
        version: str | None,
    ) -> str:
        grouped: dict[str, list[CategorisedCommit]] = {}
        for item in items:
            grouped.setdefault(item.category, []).append(item)

        lines: list[str] = []
        header = f"# Changelog — {version}" if version else "# Changelog"
        lines.append(header)
        lines.append("")

        for cat in CATEGORY_ORDER:
            cat_items = grouped.get(cat)
            if not cat_items:
                continue
            lines.append(f"## {cat}")
            lines.append("")
            for ci in cat_items:
                scope = f"**{ci.scope}**: " if ci.scope else ""
                lines.append(f"- {scope}{ci.description} (`{ci.commit_hash}`)")
            lines.append("")

        return "\n".join(lines)
