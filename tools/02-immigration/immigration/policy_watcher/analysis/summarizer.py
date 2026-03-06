"""LLM-powered change summarizer for policy diffs."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger("openclaw.immigration.policy_watcher.analysis.summarizer")

SUMMARIZE_PROMPT = """\
You are a Hong Kong immigration policy analyst. Analyse the following diff of a \
government policy document and produce a plain-language summary in 3–5 bullet points.

For each bullet point identify:
• What specifically changed
• Who is affected (applicants, sponsors, employers, specific scheme users)
• Effective date (if stated)
• Recommended action for immigration consultants

Diff:
{diff_text}

Respond ONLY with the bullet-point summary, no preamble."""


def _format_diff_for_prompt(diff_result: dict[str, Any]) -> str:
    if diff_result.get("diff_lines"):
        return "\n".join(diff_result["diff_lines"][:200])
    parts: list[str] = []
    if diff_result.get("deletions"):
        parts.append("REMOVED:")
        parts.extend(f"  - {line}" for line in diff_result["deletions"][:50])
    if diff_result.get("additions"):
        parts.append("ADDED:")
        parts.extend(f"  + {line}" for line in diff_result["additions"][:50])
    return "\n".join(parts) if parts else "(no textual diff available)"


def _structural_fallback(diff_result: dict[str, Any]) -> str:
    """Build a summary from raw diff stats when LLM is unavailable."""
    additions = diff_result.get("additions", [])
    deletions = diff_result.get("deletions", [])
    count = diff_result.get("change_count", 0)

    lines: list[str] = [f"• {count} change(s) detected in this document."]

    if deletions:
        sample = deletions[0].strip()[:120]
        lines.append(f"• Removed content includes: \"{sample}…\"")
    if additions:
        sample = additions[0].strip()[:120]
        lines.append(f"• Added content includes: \"{sample}…\"")

    lines.append("• Manual review recommended — automated LLM summary unavailable.")
    return "\n".join(lines)


async def summarize_change(diff_result: dict[str, Any], llm: Any = None) -> str:
    """Generate a 3–5 bullet point plain-language summary of a policy change.

    Falls back to a structural diff summary when the LLM provider is
    unavailable or returns an error.
    """
    if not diff_result.get("changed", True):
        return "• No substantive changes detected."

    diff_text = _format_diff_for_prompt(diff_result)

    if llm is None:
        logger.info("No LLM available, using structural fallback summary")
        return _structural_fallback(diff_result)

    try:
        prompt = SUMMARIZE_PROMPT.format(diff_text=diff_text)
        response = await llm.complete(prompt)
        summary = response if isinstance(response, str) else str(response)
        if summary and len(summary.strip()) > 20:
            return summary.strip()
        logger.warning("LLM returned empty/short summary, using fallback")
        return _structural_fallback(diff_result)
    except Exception as exc:
        logger.warning("LLM summarization failed (%s), using fallback", exc)
        return _structural_fallback(diff_result)
