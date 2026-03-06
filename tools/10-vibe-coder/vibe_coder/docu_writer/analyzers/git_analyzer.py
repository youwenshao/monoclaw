"""Git history analyser using GitPython."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass
class CommitInfo:
    hash: str
    author: str
    date: datetime
    message: str


class GitAnalyzer:
    """Read commit history from a local Git repository."""

    def get_commits(
        self,
        repo_path: str | Path,
        limit: int = 50,
    ) -> list[CommitInfo]:
        repo = self._open_repo(repo_path)
        results: list[CommitInfo] = []
        for commit in repo.iter_commits(max_count=limit):
            results.append(self._to_info(commit))
        return results

    def get_commits_between_tags(
        self,
        repo_path: str | Path,
        from_tag: str,
        to_tag: str,
    ) -> list[CommitInfo]:
        repo = self._open_repo(repo_path)
        rev_range = f"{from_tag}...{to_tag}"
        results: list[CommitInfo] = []
        for commit in repo.iter_commits(rev_range):
            results.append(self._to_info(commit))
        return results

    def get_changed_files(
        self,
        repo_path: str | Path,
        since_commit: str | None = None,
        limit: int = 50,
    ) -> list[str]:
        """Return deduplicated list of files changed in recent commits."""
        repo = self._open_repo(repo_path)
        changed: set[str] = set()
        kwargs: dict = {"max_count": limit}
        if since_commit:
            kwargs["rev"] = f"{since_commit}..HEAD"
        for commit in repo.iter_commits(**kwargs):
            changed.update(commit.stats.files.keys())
        return sorted(changed)

    # ------------------------------------------------------------------

    @staticmethod
    def _open_repo(repo_path: str | Path):
        import git

        return git.Repo(str(repo_path), search_parent_directories=True)

    @staticmethod
    def _to_info(commit) -> CommitInfo:
        return CommitInfo(
            hash=commit.hexsha[:12],
            author=str(commit.author),
            date=datetime.fromtimestamp(commit.committed_date),
            message=commit.message.strip(),
        )
