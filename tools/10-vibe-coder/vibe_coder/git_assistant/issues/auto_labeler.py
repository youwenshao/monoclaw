"""Auto-label GitHub issues using LLM classification."""

from __future__ import annotations

import json
from dataclasses import dataclass

from openclaw_shared.llm.base import LLMProvider
from vibe_coder.git_assistant.issues.issue_fetcher import Issue


@dataclass
class LabelSuggestion:
    name: str
    confidence: float


SYSTEM_PROMPT = (
    "You are a GitHub issue triage bot. Suggest labels from the provided list. "
    "Respond ONLY with a JSON array of objects with 'name' and 'confidence' keys. "
    "Confidence is a float between 0 and 1."
)

LABEL_PROMPT_TEMPLATE = """\
Given this GitHub issue, suggest appropriate labels.

Issue #{number}: {title}

{body}

Available labels: {labels}

Respond with a JSON array like: [{{"name": "bug", "confidence": 0.95}}]
Only suggest labels from the available list. Max 5 labels.
"""


class AutoLabeler:
    """Suggest labels for a GitHub issue using LLM classification."""

    async def suggest_labels(
        self,
        issue: Issue,
        available_labels: list[str],
        llm: LLMProvider,
    ) -> list[LabelSuggestion]:
        if not available_labels:
            return []

        prompt = LABEL_PROMPT_TEMPLATE.format(
            number=issue.number,
            title=issue.title,
            body=issue.body[:2000] if issue.body else "(no description)",
            labels=", ".join(available_labels),
        )

        raw = await llm.generate(
            prompt,
            system=SYSTEM_PROMPT,
            max_tokens=256,
            temperature=0.2,
        )

        return self._parse_response(raw, available_labels)

    @staticmethod
    def _parse_response(raw: str, available_labels: list[str]) -> list[LabelSuggestion]:
        available_set = {lbl.lower() for lbl in available_labels}
        label_map = {lbl.lower(): lbl for lbl in available_labels}

        text = raw.strip()
        start = text.find("[")
        end = text.rfind("]")
        if start == -1 or end == -1:
            return []

        try:
            items = json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            return []

        suggestions: list[LabelSuggestion] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name", "")).strip()
            confidence = float(item.get("confidence", 0.0))
            if name.lower() in available_set:
                suggestions.append(
                    LabelSuggestion(
                        name=label_map[name.lower()],
                        confidence=min(max(confidence, 0.0), 1.0),
                    )
                )

        suggestions.sort(key=lambda s: s.confidence, reverse=True)
        return suggestions[:5]
