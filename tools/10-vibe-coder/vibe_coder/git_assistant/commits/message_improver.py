"""Improve commit messages using LLM to follow conventional commits format."""

from __future__ import annotations

from openclaw_shared.llm.base import LLMProvider
from vibe_coder.git_assistant.commits.conventional_commits import (
    ConventionalCommit,
    parse_conventional,
)
from vibe_coder.git_assistant.pr.diff_analyzer import DiffSummary

SYSTEM_PROMPT = (
    "You are a git commit message expert. Rewrite the given commit message "
    "to follow the Conventional Commits specification. "
    "Output ONLY the improved commit message, nothing else."
)

IMPROVE_PROMPT_TEMPLATE = """\
Rewrite this commit message to follow Conventional Commits format.

Original message: {message}

Diff context:
- Files changed: {files_changed}
- Insertions: {insertions}
- Deletions: {deletions}
- Key files: {key_files}

Rules:
- Use one of: feat, fix, chore, docs, refactor, test, ci, perf, style, build
- Include scope in parentheses if the change targets a specific module
- Add "!" before ":" if it's a breaking change
- Keep the description concise (under 72 chars)
- Add a body paragraph only if the change needs explanation

Output ONLY the improved message.
"""


class CommitMessageImprover:
    """Rewrite commit messages into conventional commits format."""

    async def improve(
        self,
        message: str,
        diff_summary: DiffSummary,
        llm: LLMProvider,
    ) -> str:
        existing = parse_conventional(message)
        if existing and self._is_well_formed(existing):
            return message.strip()

        key_files = ", ".join(
            f.path for f in diff_summary.file_summaries[:5]
        )

        prompt = IMPROVE_PROMPT_TEMPLATE.format(
            message=message.strip(),
            files_changed=diff_summary.files_changed,
            insertions=diff_summary.insertions,
            deletions=diff_summary.deletions,
            key_files=key_files or "(unknown)",
        )

        improved = await llm.generate(
            prompt,
            system=SYSTEM_PROMPT,
            max_tokens=256,
            temperature=0.3,
        )

        result = improved.strip().strip("`").strip()
        if not parse_conventional(result):
            return f"chore: {result.splitlines()[0]}" if result else message.strip()
        return result

    @staticmethod
    def _is_well_formed(commit: ConventionalCommit) -> bool:
        return bool(commit.type and commit.description and len(commit.description) <= 72)
