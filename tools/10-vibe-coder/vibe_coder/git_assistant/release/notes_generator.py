"""Generate formatted release notes from categorized commits."""

from __future__ import annotations

from openclaw_shared.llm.base import LLMProvider
from vibe_coder.git_assistant.release.commit_analyzer import CategorizedCommits

SYSTEM_PROMPT = (
    "You are a release manager writing clear, professional release notes. "
    "Output well-formatted Markdown suitable for a GitHub release."
)

NOTES_PROMPT_TEMPLATE = """\
Write release notes for version {version}.

Breaking changes:
{breaking}

New features:
{features}

Bug fixes:
{fixes}

Improvements:
{improvements}

Other:
{other}

Format as Markdown with these sections (omit empty sections):
# Release {version}
## Breaking Changes
## Features
## Bug Fixes
## Improvements
## Other
"""


class ReleaseNotesGenerator:
    """Generate polished release notes with optional LLM enhancement."""

    async def generate(
        self,
        categorized_commits: CategorizedCommits,
        version: str,
        llm: LLMProvider,
    ) -> str:
        breaking = self._format_list(categorized_commits.breaking)
        features = self._format_list(categorized_commits.features)
        fixes = self._format_list(categorized_commits.fixes)
        improvements = self._format_list(categorized_commits.improvements)
        other = self._format_list(categorized_commits.other)

        prompt = NOTES_PROMPT_TEMPLATE.format(
            version=version,
            breaking=breaking or "(none)",
            features=features or "(none)",
            fixes=fixes or "(none)",
            improvements=improvements or "(none)",
            other=other or "(none)",
        )

        notes = await llm.generate(
            prompt,
            system=SYSTEM_PROMPT,
            max_tokens=1024,
            temperature=0.3,
        )

        return notes.strip()

    @staticmethod
    def _format_list(commits: list) -> str:
        if not commits:
            return ""
        lines: list[str] = []
        for c in commits:
            scope_part = f"**{c.scope}**: " if c.scope else ""
            lines.append(f"- {scope_part}{c.description} ({c.hash[:8]})")
        return "\n".join(lines)
