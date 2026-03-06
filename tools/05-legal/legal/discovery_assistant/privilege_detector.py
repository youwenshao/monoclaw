"""Privilege detection via keyword pre-filter and LLM semantic classification."""

from __future__ import annotations

import json
import re
from typing import Any

PRIVILEGE_KEYWORDS: list[tuple[str, str]] = [
    (r"\bprivileged\b", "general_privilege"),
    (r"\bsolicitor[\s-]client\b", "legal_professional_privilege"),
    (r"\blegal[\s-]?professional[\s-]?privilege\b", "legal_professional_privilege"),
    (r"\blegal\s+advice\b", "legal_professional_privilege"),
    (r"\battorney[\s-]client\b", "legal_professional_privilege"),
    (r"\bwithout\s+prejudice\b", "without_prejudice"),
    (r"\blitigation\s+privilege\b", "litigation_privilege"),
    (r"\bwork[\s-]?product\b", "litigation_privilege"),
    (r"\bin\s+contemplation\s+of\s+litigation\b", "litigation_privilege"),
    (r"\bdominant\s+purpose\b", "litigation_privilege"),
    (r"\bconfidential\s+communication\b", "general_privilege"),
    (r"\bprivileged\s+and\s+confidential\b", "general_privilege"),
    (r"\blegal\s+professional\b", "legal_professional_privilege"),
    (r"\bsettlement\s+negotiation\b", "without_prejudice"),
]

LLM_SYSTEM_PROMPT = (
    "You are a Hong Kong legal privilege classifier. Given the text of a document, "
    "determine whether it is protected by legal privilege under Hong Kong law.\n\n"
    "Categories:\n"
    "- legal_professional_privilege: communications between solicitor and client "
    "for the purpose of giving/receiving legal advice\n"
    "- litigation_privilege: documents created for the dominant purpose of pending "
    "or contemplated litigation\n"
    "- without_prejudice: communications made in genuine attempts to settle a dispute\n"
    "- none: no privilege applies\n\n"
    "Respond ONLY with a JSON object having these keys:\n"
    '  "privilege_status": one of "privileged", "not_privileged", "partial", "needs_review"\n'
    '  "privilege_type": the category string or null\n'
    '  "confidence_score": float 0.0 to 1.0\n'
    '  "reasoning": brief explanation'
)


def _keyword_scan(text: str) -> list[dict[str, str]]:
    """Scan text for privilege-indicating keywords. Return matches with types."""
    text_lower = text.lower()
    hits: list[dict[str, str]] = []
    seen_types: set[str] = set()
    for pattern, priv_type in PRIVILEGE_KEYWORDS:
        if re.search(pattern, text_lower):
            if priv_type not in seen_types:
                hits.append({"pattern": pattern, "privilege_type": priv_type})
                seen_types.add(priv_type)
    return hits


def _build_llm_prompt(document: dict[str, Any], keyword_hits: list[dict[str, str]]) -> str:
    parts = [
        f"Subject: {document.get('subject', 'N/A')}",
        f"From: {document.get('author', document.get('from', 'N/A'))}",
        f"To: {document.get('recipients', document.get('to', 'N/A'))}",
        f"Date: {document.get('date_created', document.get('date', 'N/A'))}",
        "",
        "Document text:",
        (document.get("body_text", "") or "")[:3000],
    ]

    if keyword_hits:
        parts.append("")
        parts.append("Pre-filter keyword matches found:")
        for hit in keyword_hits:
            parts.append(f"  - {hit['privilege_type']}")

    parts.append("")
    parts.append("Classify the privilege status of this document.")
    return "\n".join(parts)


def _parse_llm_response(raw: str) -> dict[str, Any]:
    """Best-effort extraction of JSON from the LLM output."""
    raw = raw.strip()
    start = raw.find("{")
    end = raw.rfind("}") + 1
    if start >= 0 and end > start:
        try:
            return json.loads(raw[start:end])
        except json.JSONDecodeError:
            pass
    return {}


async def detect_privilege(document: dict[str, Any], llm: Any = None) -> dict[str, Any]:
    """Two-stage privilege detection: keyword scan then optional LLM classification.

    Returns dict with:
      - privilege_status: privileged | not_privileged | partial | needs_review
      - privilege_type: str | None
      - confidence_score: float
      - keyword_hits: list of matched patterns
    """
    text = " ".join(
        filter(None, [
            document.get("subject", ""),
            document.get("body_text", ""),
        ])
    )

    keyword_hits = _keyword_scan(text)

    if not keyword_hits:
        return {
            "privilege_status": "not_privileged",
            "privilege_type": None,
            "confidence_score": 0.85,
            "keyword_hits": [],
        }

    if llm is None:
        primary_type = keyword_hits[0]["privilege_type"]
        return {
            "privilege_status": "needs_review",
            "privilege_type": primary_type,
            "confidence_score": 0.50,
            "keyword_hits": keyword_hits,
        }

    prompt = _build_llm_prompt(document, keyword_hits)
    try:
        raw_response = await llm.generate(
            prompt,
            system=LLM_SYSTEM_PROMPT,
            max_tokens=300,
            temperature=0.1,
        )
        parsed = _parse_llm_response(raw_response)

        status = parsed.get("privilege_status", "needs_review")
        if status not in ("privileged", "not_privileged", "partial", "needs_review"):
            status = "needs_review"

        priv_type = parsed.get("privilege_type")
        confidence = parsed.get("confidence_score", 0.5)
        if not isinstance(confidence, (int, float)):
            confidence = 0.5
        confidence = max(0.0, min(1.0, float(confidence)))

        return {
            "privilege_status": status,
            "privilege_type": priv_type,
            "confidence_score": confidence,
            "keyword_hits": keyword_hits,
        }
    except Exception:
        primary_type = keyword_hits[0]["privilege_type"]
        return {
            "privilege_status": "needs_review",
            "privilege_type": primary_type,
            "confidence_score": 0.40,
            "keyword_hits": keyword_hits,
        }
