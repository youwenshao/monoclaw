"""SemVer version bump suggestions based on commit categories."""

from __future__ import annotations

import re

from vibe_coder.git_assistant.release.commit_analyzer import CategorizedCommits

_SEMVER_RE = re.compile(
    r"^v?(?P<major>\d+)\.(?P<minor>\d+)\.(?P<patch>\d+)"
    r"(?:-(?P<pre>[a-zA-Z0-9.]+))?$"
)


class VersionHelper:
    """Suggest the next semantic version based on categorized commits."""

    def suggest_version(
        self,
        current_version: str,
        categorized_commits: CategorizedCommits,
    ) -> str:
        major, minor, patch = self._parse(current_version)

        if categorized_commits.breaking:
            return f"{major + 1}.0.0"
        if categorized_commits.features:
            return f"{major}.{minor + 1}.0"
        if categorized_commits.fixes or categorized_commits.improvements:
            return f"{major}.{minor}.{patch + 1}"

        return f"{major}.{minor}.{patch + 1}"

    @staticmethod
    def _parse(version: str) -> tuple[int, int, int]:
        match = _SEMVER_RE.match(version.strip())
        if not match:
            raise ValueError(f"Invalid semver string: {version!r}")
        return (
            int(match.group("major")),
            int(match.group("minor")),
            int(match.group("patch")),
        )
