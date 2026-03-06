"""Categorize commits by conventional-commit type."""

from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class ParsedCommit:
    hash: str
    message: str
    type: str
    scope: str
    description: str
    breaking: bool


@dataclass
class CategorizedCommits:
    features: list[ParsedCommit] = field(default_factory=list)
    fixes: list[ParsedCommit] = field(default_factory=list)
    breaking: list[ParsedCommit] = field(default_factory=list)
    improvements: list[ParsedCommit] = field(default_factory=list)
    other: list[ParsedCommit] = field(default_factory=list)


_CONVENTIONAL_RE = re.compile(
    r"^(?P<type>feat|fix|chore|docs|refactor|test|ci|perf|style|build)"
    r"(?:\((?P<scope>[^)]+)\))?"
    r"(?P<breaking>!)?"
    r":\s*(?P<description>.+)$",
    re.IGNORECASE,
)

_IMPROVEMENT_TYPES = {"refactor", "perf", "style", "build", "chore", "ci", "docs", "test"}


class CommitAnalyzer:
    """Parse and categorize a list of commit messages."""

    def categorize(self, commits: list[dict[str, str]]) -> CategorizedCommits:
        """Categorize commits.

        Each commit dict should have at minimum ``hash`` and ``message`` keys.
        """
        result = CategorizedCommits()

        for commit in commits:
            sha = commit.get("hash", "")
            message = commit.get("message", "").strip()
            first_line = message.splitlines()[0] if message else ""

            parsed = self._parse_one(sha, first_line, message)

            if parsed.breaking:
                result.breaking.append(parsed)

            if parsed.type == "feat":
                result.features.append(parsed)
            elif parsed.type == "fix":
                result.fixes.append(parsed)
            elif parsed.type in _IMPROVEMENT_TYPES:
                result.improvements.append(parsed)
            else:
                result.other.append(parsed)

        return result

    @staticmethod
    def _parse_one(sha: str, first_line: str, full_message: str) -> ParsedCommit:
        match = _CONVENTIONAL_RE.match(first_line)
        if match:
            is_breaking = bool(match.group("breaking")) or "BREAKING CHANGE" in full_message
            return ParsedCommit(
                hash=sha,
                message=full_message,
                type=match.group("type").lower(),
                scope=match.group("scope") or "",
                description=match.group("description").strip(),
                breaking=is_breaking,
            )

        return ParsedCommit(
            hash=sha,
            message=full_message,
            type="other",
            scope="",
            description=first_line,
            breaking="BREAKING CHANGE" in full_message,
        )
