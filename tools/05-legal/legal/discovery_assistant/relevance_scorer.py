"""Document relevance tier assignment via keyword matching and LLM."""

from __future__ import annotations

import json
from typing import Any

LLM_SYSTEM_PROMPT = (
    "You are a legal e-discovery relevance scorer. Given a document and a list of "
    "case-relevant keywords, classify the document into one of three relevance tiers.\n\n"
    "Tiers:\n"
    "- directly_relevant: document directly pertains to the issues in dispute, "
    "contains key evidence or admissions\n"
    "- potentially_relevant: document has some connection to the case but may not "
    "be directly probative\n"
    "- not_relevant: document has no meaningful connection to the case issues\n\n"
    "Respond ONLY with a JSON object having these keys:\n"
    '  "relevance_tier": one of "directly_relevant", "potentially_relevant", "not_relevant"\n'
    '  "confidence_score": float 0.0 to 1.0\n'
    '  "reasoning": brief explanation of the classification'
)


def _keyword_overlap_score(text: str, case_keywords: list[str]) -> float:
    """Compute fraction of case keywords found in the document text."""
    if not case_keywords:
        return 0.0
    text_lower = text.lower()
    matches = sum(1 for kw in case_keywords if kw.lower() in text_lower)
    return matches / len(case_keywords)


def _build_prompt(document: dict[str, Any], case_keywords: list[str]) -> str:
    parts = [
        f"Subject: {document.get('subject', 'N/A')}",
        f"From: {document.get('author', document.get('from', 'N/A'))}",
        f"To: {document.get('recipients', document.get('to', 'N/A'))}",
        f"Date: {document.get('date_created', document.get('date', 'N/A'))}",
        f"Document type: {document.get('doc_type', 'N/A')}",
        "",
        "Document text (truncated):",
        (document.get("body_text", "") or "")[:3000],
        "",
        f"Case-relevant keywords: {', '.join(case_keywords)}",
        "",
        "Classify the relevance of this document to the case.",
    ]
    return "\n".join(parts)


def _parse_llm_response(raw: str) -> dict[str, Any]:
    raw = raw.strip()
    start = raw.find("{")
    end = raw.rfind("}") + 1
    if start >= 0 and end > start:
        try:
            return json.loads(raw[start:end])
        except json.JSONDecodeError:
            pass
    return {}


async def score_relevance(
    document: dict[str, Any],
    case_keywords: list[str],
    llm: Any = None,
) -> dict[str, Any]:
    """Score a document's relevance to a case.

    Returns dict with:
      - relevance_tier: directly_relevant | potentially_relevant | not_relevant
      - confidence_score: float
      - keyword_overlap: float (fraction of case keywords found)
    """
    text = " ".join(
        filter(None, [
            document.get("subject", ""),
            document.get("body_text", ""),
        ])
    )

    overlap = _keyword_overlap_score(text, case_keywords)

    if llm is None:
        if overlap >= 0.5:
            tier = "directly_relevant"
            confidence = 0.6 + overlap * 0.3
        elif overlap >= 0.2:
            tier = "potentially_relevant"
            confidence = 0.5 + overlap * 0.2
        else:
            tier = "not_relevant"
            confidence = 0.7
        return {
            "relevance_tier": tier,
            "confidence_score": round(min(confidence, 1.0), 2),
            "keyword_overlap": round(overlap, 2),
        }

    prompt = _build_prompt(document, case_keywords)
    try:
        raw_response = await llm.generate(
            prompt,
            system=LLM_SYSTEM_PROMPT,
            max_tokens=300,
            temperature=0.1,
        )
        parsed = _parse_llm_response(raw_response)

        tier = parsed.get("relevance_tier", "not_relevant")
        if tier not in ("directly_relevant", "potentially_relevant", "not_relevant"):
            tier = "not_relevant"

        confidence = parsed.get("confidence_score", 0.5)
        if not isinstance(confidence, (int, float)):
            confidence = 0.5
        confidence = max(0.0, min(1.0, float(confidence)))

        return {
            "relevance_tier": tier,
            "confidence_score": round(confidence, 2),
            "keyword_overlap": round(overlap, 2),
        }
    except Exception:
        if overlap >= 0.5:
            tier = "directly_relevant"
        elif overlap >= 0.2:
            tier = "potentially_relevant"
        else:
            tier = "not_relevant"
        return {
            "relevance_tier": tier,
            "confidence_score": 0.4,
            "keyword_overlap": round(overlap, 2),
        }
