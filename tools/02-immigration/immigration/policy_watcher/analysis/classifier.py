"""Urgency classification for policy changes."""

from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger("openclaw.immigration.policy_watcher.analysis.classifier")

SCHEME_KEYWORDS: dict[str, list[str]] = {
    "GEP": ["general employment policy", "gep", "employment policy"],
    "ASMTP": [
        "admission scheme for mainland talents",
        "asmtp",
        "mainland talent",
        "mainland professionals",
    ],
    "QMAS": ["quality migrant", "qmas", "points-based", "point-based"],
    "TTPS": ["top talent pass", "ttps", "high earner", "top talent"],
    "TechTAS": ["technology talent", "techtas", "tech talent"],
    "IANG": [
        "immigration arrangements for non-local graduates",
        "iang",
        "non-local graduate",
    ],
}

URGENT_PATTERNS = [
    r"quota.{0,20}(?:suspend|halt|reduc|cut|eliminat|zero)",
    r"scheme.{0,20}(?:suspend|terminat|discontinu|clos|halt)",
    r"(?:immediate|with immediate effect)",
    r"(?:suspend|terminat)\w*\s+(?:of|the)\s+scheme",
    r"(?:moratorium|freeze|ban)\s+on",
]

IMPORTANT_PATTERNS = [
    r"(?:salary|wage|income).{0,20}(?:threshold|requirement|minimum|increase|rais|adjust)",
    r"eligib\w+.{0,20}(?:change|amend|revis|tighten|relax|expand|narrow)",
    r"(?:processing|approval).{0,20}(?:time|period|duration).{0,20}(?:change|extend|shorten)",
    r"(?:new|additional|revised).{0,15}(?:requirement|document|criteria|condition)",
    r"(?:age|experience|qualification).{0,20}(?:change|amend|revis)",
    r"(?:dependant|dependent).{0,20}(?:polic|rule|change)",
    r"(?:fee|charge|cost).{0,20}(?:increase|rais|adjust|change)",
]

_URGENT_RE = [re.compile(p, re.IGNORECASE) for p in URGENT_PATTERNS]
_IMPORTANT_RE = [re.compile(p, re.IGNORECASE) for p in IMPORTANT_PATTERNS]

CLASSIFY_PROMPT = """\
You are a Hong Kong immigration policy analyst. Classify the urgency of the \
following policy change for immigration consultants.

Change summary:
{summary}

Affected schemes: {schemes}

Return EXACTLY one word: "urgent", "important", or "routine".

Rules:
- urgent: quota changes, scheme suspension/termination, immediate-effect changes
- important: eligibility changes, salary threshold changes, new requirements, fee changes
- routine: procedural updates, administrative notices, minor clarifications"""


def detect_affected_schemes(text: str) -> list[str]:
    """Detect which immigration schemes are mentioned in the text."""
    lower = text.lower()
    found: list[str] = []
    for scheme, keywords in SCHEME_KEYWORDS.items():
        if any(kw in lower for kw in keywords):
            found.append(scheme)
    return found


def _rule_based_classify(text: str) -> str | None:
    """Apply deterministic rules before falling back to LLM."""
    for pattern in _URGENT_RE:
        if pattern.search(text):
            return "urgent"
    for pattern in _IMPORTANT_RE:
        if pattern.search(text):
            return "important"
    return None


def classify_urgency(
    change_summary: str,
    affected_schemes: str,
    llm: Any = None,
) -> str:
    """Classify a policy change as 'routine', 'important', or 'urgent'.

    Applies deterministic keyword rules first. Falls back to LLM classification
    if no rule matches and an LLM provider is available.
    """
    combined = f"{change_summary} {affected_schemes}"
    rule_result = _rule_based_classify(combined)
    if rule_result:
        logger.debug("Rule-based classification: %s", rule_result)
        return rule_result

    if llm is not None:
        try:
            prompt = CLASSIFY_PROMPT.format(
                summary=change_summary,
                schemes=affected_schemes,
            )
            import asyncio

            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    result = pool.submit(asyncio.run, llm.complete(prompt)).result()
            else:
                result = asyncio.run(llm.complete(prompt))

            answer = str(result).strip().lower()
            if answer in ("urgent", "important", "routine"):
                return answer
            logger.warning("LLM returned unexpected urgency value: %r", answer)
        except Exception as exc:
            logger.warning("LLM classification failed (%s), defaulting to routine", exc)

    return "routine"
