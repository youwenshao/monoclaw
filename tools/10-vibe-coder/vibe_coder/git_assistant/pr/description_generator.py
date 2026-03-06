"""LLM-powered PR description generator."""

from __future__ import annotations

from dataclasses import dataclass

from openclaw_shared.llm.base import LLMProvider
from vibe_coder.git_assistant.pr.diff_analyzer import DiffSummary


@dataclass
class PRDescription:
    title: str
    body: str


SYSTEM_PROMPT = (
    "You are a senior developer writing clear, concise pull request descriptions. "
    "Follow the exact output format provided."
)

PR_PROMPT_TEMPLATE = """\
Generate a pull request title and body for the following diff summary.

Files changed: {files_changed}
Insertions: {insertions}
Deletions: {deletions}

Per-file changes:
{per_file}

Output format (use these exact headers):

TITLE: <one-line PR title using conventional commit style>

## Summary
<2-3 sentence overview>

## Motivation
<why this change is needed>

## Changes
<bullet list of key changes>

## Test Plan
<bullet list of testing steps>
"""


class PRDescriptionGenerator:
    """Generate structured PR descriptions from diff summaries using an LLM."""

    async def generate(
        self,
        diff_summary: DiffSummary,
        llm: LLMProvider,
    ) -> PRDescription:
        per_file = "\n".join(
            f"  {f.change_type:>8} {f.path} (+{f.insertions}/-{f.deletions})"
            for f in diff_summary.file_summaries
        )

        prompt = PR_PROMPT_TEMPLATE.format(
            files_changed=diff_summary.files_changed,
            insertions=diff_summary.insertions,
            deletions=diff_summary.deletions,
            per_file=per_file or "(no file details available)",
        )

        raw = await llm.generate(
            prompt,
            system=SYSTEM_PROMPT,
            max_tokens=1024,
            temperature=0.4,
        )

        return self._parse_response(raw)

    @staticmethod
    def _parse_response(raw: str) -> PRDescription:
        lines = raw.strip().splitlines()
        title = ""
        body_lines: list[str] = []
        parsing_body = False

        for line in lines:
            if line.startswith("TITLE:"):
                title = line.removeprefix("TITLE:").strip()
                continue
            if line.startswith("## "):
                parsing_body = True
            if parsing_body:
                body_lines.append(line)

        if not title:
            title = lines[0] if lines else "Update"

        body = "\n".join(body_lines).strip()
        if not body:
            body = raw.strip()

        return PRDescription(title=title, body=body)
