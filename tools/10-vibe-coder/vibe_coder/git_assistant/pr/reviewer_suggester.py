"""Suggest PR reviewers based on code ownership signals."""

from __future__ import annotations

import subprocess
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ReviewerSuggestion:
    email: str
    score: float
    files_owned: list[str] = field(default_factory=list)


RECENT_COMMIT_WEIGHT = 0.6
BLAME_LINES_WEIGHT = 0.4


class ReviewerSuggester:
    """Compute ownership scores and suggest reviewers for a set of changed files."""

    def suggest(
        self,
        repo_path: str | Path,
        changed_files: list[str],
        count: int = 3,
    ) -> list[ReviewerSuggestion]:
        repo = Path(repo_path).expanduser().resolve()
        if not (repo / ".git").exists():
            raise ValueError(f"Not a git repository: {repo}")

        commit_scores: dict[str, float] = defaultdict(float)
        blame_scores: dict[str, float] = defaultdict(float)
        ownership: dict[str, list[str]] = defaultdict(list)

        for filepath in changed_files:
            full_path = repo / filepath
            if not full_path.exists():
                continue

            recent = self._recent_commit_authors(repo, filepath)
            for email, weight in recent.items():
                commit_scores[email] += weight
                if filepath not in ownership[email]:
                    ownership[email].append(filepath)

            blame = self._blame_ownership(repo, filepath)
            for email, fraction in blame.items():
                blame_scores[email] += fraction
                if filepath not in ownership[email]:
                    ownership[email].append(filepath)

        all_authors = set(commit_scores) | set(blame_scores)
        if not all_authors:
            return []

        max_commit = max(commit_scores.values()) if commit_scores else 1.0
        max_blame = max(blame_scores.values()) if blame_scores else 1.0

        scored: list[ReviewerSuggestion] = []
        for email in all_authors:
            norm_commit = commit_scores.get(email, 0.0) / max_commit if max_commit else 0
            norm_blame = blame_scores.get(email, 0.0) / max_blame if max_blame else 0
            score = RECENT_COMMIT_WEIGHT * norm_commit + BLAME_LINES_WEIGHT * norm_blame
            scored.append(
                ReviewerSuggestion(
                    email=email,
                    score=round(score, 4),
                    files_owned=ownership.get(email, []),
                )
            )

        scored.sort(key=lambda r: r.score, reverse=True)
        return scored[:count]

    def _recent_commit_authors(
        self, repo: Path, filepath: str, max_commits: int = 20
    ) -> dict[str, float]:
        """Weight recent committers with exponential decay."""
        try:
            output = self._run_git(
                repo, "log", f"-{max_commits}", "--format=%ae", "--follow", "--", filepath
            )
        except RuntimeError:
            return {}

        authors: dict[str, float] = defaultdict(float)
        lines = [l for l in output.strip().splitlines() if l.strip()]
        for idx, email in enumerate(lines):
            decay = 1.0 / (1 + idx * 0.3)
            authors[email.strip()] += decay
        return dict(authors)

    def _blame_ownership(self, repo: Path, filepath: str) -> dict[str, float]:
        """Fraction of lines each author owns via git blame."""
        try:
            output = self._run_git(repo, "blame", "--line-porcelain", "--", filepath)
        except RuntimeError:
            return {}

        line_counts: dict[str, int] = defaultdict(int)
        total = 0
        for line in output.splitlines():
            if line.startswith("author-mail "):
                email = line.removeprefix("author-mail ").strip().strip("<>")
                if email and email != "not.committed.yet":
                    line_counts[email] += 1
                    total += 1

        if total == 0:
            return {}
        return {email: count / total for email, count in line_counts.items()}

    @staticmethod
    def _run_git(repo: Path, *args: str) -> str:
        result = subprocess.run(
            ["git", *args],
            cwd=str(repo),
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            raise RuntimeError(f"git {args[0]} failed: {result.stderr.strip()}")
        return result.stdout
