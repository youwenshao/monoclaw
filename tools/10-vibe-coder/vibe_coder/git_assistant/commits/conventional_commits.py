"""Conventional commits parsing and formatting utilities."""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class ConventionalCommit:
    type: str
    scope: str
    description: str
    breaking: bool
    body: str


_CONVENTIONAL_RE = re.compile(
    r"^(?P<type>[a-z]+)"
    r"(?:\((?P<scope>[^)]+)\))?"
    r"(?P<breaking>!)?"
    r":\s*(?P<description>.+)$",
    re.IGNORECASE,
)

VALID_TYPES = frozenset(
    {"feat", "fix", "chore", "docs", "refactor", "test", "ci", "perf", "style", "build"}
)


def parse_conventional(message: str) -> ConventionalCommit | None:
    """Parse a commit message into its conventional-commit components.

    Returns ``None`` if the message does not follow conventional commits format.
    """
    lines = message.strip().splitlines()
    if not lines:
        return None

    first_line = lines[0].strip()
    match = _CONVENTIONAL_RE.match(first_line)
    if not match:
        return None

    commit_type = match.group("type").lower()
    if commit_type not in VALID_TYPES:
        return None

    body = "\n".join(lines[2:]).strip() if len(lines) > 2 else ""
    is_breaking = bool(match.group("breaking")) or "BREAKING CHANGE" in body

    return ConventionalCommit(
        type=commit_type,
        scope=match.group("scope") or "",
        description=match.group("description").strip(),
        breaking=is_breaking,
        body=body,
    )


def format_conventional(
    type: str,
    scope: str = "",
    description: str = "",
    breaking: bool = False,
    body: str = "",
) -> str:
    """Format a conventional commit message from components."""
    scope_part = f"({scope})" if scope else ""
    breaking_part = "!" if breaking else ""
    header = f"{type}{scope_part}{breaking_part}: {description}"

    if body:
        return f"{header}\n\n{body}"
    return header
