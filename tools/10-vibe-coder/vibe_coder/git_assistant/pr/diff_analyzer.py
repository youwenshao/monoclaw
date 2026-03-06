"""Parse and summarize git diffs between branches."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class FileDiff:
    path: str
    insertions: int
    deletions: int
    change_type: str  # "added", "modified", "deleted", "renamed"


@dataclass
class DiffSummary:
    files_changed: int
    insertions: int
    deletions: int
    file_summaries: list[FileDiff] = field(default_factory=list)
    truncated: bool = False


LARGE_DIFF_THRESHOLD = 500


class DiffAnalyzer:
    """Analyze git diffs between two branches in a repository."""

    def analyze(
        self,
        repo_path: str | Path,
        base_branch: str,
        head_branch: str,
    ) -> DiffSummary:
        repo = Path(repo_path).expanduser().resolve()
        if not (repo / ".git").exists():
            raise ValueError(f"Not a git repository: {repo}")

        numstat = self._run_git(
            repo, "diff", "--numstat", f"{base_branch}...{head_branch}"
        )
        name_status = self._run_git(
            repo, "diff", "--name-status", f"{base_branch}...{head_branch}"
        )

        change_types = self._parse_name_status(name_status)
        file_summaries: list[FileDiff] = []
        total_ins = 0
        total_del = 0

        for line in numstat.strip().splitlines():
            if not line.strip():
                continue
            parts = line.split("\t", 2)
            if len(parts) < 3:
                continue
            ins_str, del_str, path = parts
            ins = int(ins_str) if ins_str != "-" else 0
            dels = int(del_str) if del_str != "-" else 0
            total_ins += ins
            total_del += dels
            file_summaries.append(
                FileDiff(
                    path=path,
                    insertions=ins,
                    deletions=dels,
                    change_type=change_types.get(path, "modified"),
                )
            )

        total_lines = total_ins + total_del
        truncated = total_lines > LARGE_DIFF_THRESHOLD

        if truncated:
            file_summaries = self._summarize_large_diff(file_summaries)

        return DiffSummary(
            files_changed=len(file_summaries),
            insertions=total_ins,
            deletions=total_del,
            file_summaries=file_summaries,
            truncated=truncated,
        )

    def _summarize_large_diff(self, files: list[FileDiff]) -> list[FileDiff]:
        """Keep per-file stats but sort by magnitude for large diffs."""
        return sorted(files, key=lambda f: f.insertions + f.deletions, reverse=True)

    @staticmethod
    def _parse_name_status(output: str) -> dict[str, str]:
        status_map = {"A": "added", "M": "modified", "D": "deleted", "R": "renamed"}
        result: dict[str, str] = {}
        for line in output.strip().splitlines():
            if not line.strip():
                continue
            parts = line.split("\t")
            status_code = parts[0][0] if parts[0] else "M"
            path = parts[-1]
            result[path] = status_map.get(status_code, "modified")
        return result

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
