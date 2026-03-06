"""Anomaly detection — deviation scoring against reference clause templates."""

from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger("openclaw.legal.doc_analyzer.anomaly_detector")

CRITICAL_KEYWORDS: dict[str, list[str]] = {
    "indemnity": ["unlimited", "whatsoever", "howsoever", "all losses"],
    "liability_cap": ["unlimited liability", "no cap", "without limit"],
    "non_compete": ["worldwide", "24 month", "36 month", "perpetual"],
    "termination": ["immediate termination", "without cause", "sole discretion"],
    "rent_review": ["15%", "20%", "market rate at landlord's discretion"],
    "confidentiality": ["perpetual", "unlimited duration", "survive indefinitely"],
}

ONE_SIDED_INDICATORS = [
    "the tenant shall", "the employee shall", "the recipient shall",
    "without reciprocal", "sole obligation",
]

UNUSUAL_DURATION_RE = re.compile(
    r"(\d+)\s*(?:month|year)s?",
    re.IGNORECASE,
)


def _keyword_deviation_score(clause_text: str, clause_type: str) -> tuple[float, list[str]]:
    """Score deviation based on presence of critical keywords. Returns (score, reasons)."""
    text_lower = clause_text.lower()
    reasons: list[str] = []
    hits = 0
    total_checks = 0

    critical = CRITICAL_KEYWORDS.get(clause_type, [])
    for kw in critical:
        total_checks += 1
        if kw.lower() in text_lower:
            hits += 1
            reasons.append(f"Contains critical keyword: '{kw}'")

    for indicator in ONE_SIDED_INDICATORS:
        total_checks += 1
        if indicator.lower() in text_lower:
            hits += 1
            reasons.append(f"One-sided obligation detected: '{indicator}'")

    if clause_type == "non_compete":
        for m in UNUSUAL_DURATION_RE.finditer(clause_text):
            duration_val = int(m.group(1))
            unit_text = m.group(0).lower()
            months = duration_val * 12 if "year" in unit_text else duration_val
            if months > 12:
                hits += 2
                reasons.append(
                    f"Non-compete duration of {months} months exceeds typical HK enforceable range (6-12 months)"
                )

    if clause_type == "rent_review":
        pct_match = re.search(r"(\d+(?:\.\d+)?)\s*%", clause_text)
        if pct_match:
            pct = float(pct_match.group(1))
            if pct > 10:
                hits += 2
                reasons.append(
                    f"Rent escalation of {pct}% exceeds typical HK market standard of 10%"
                )

    if total_checks == 0:
        return 0.0, reasons
    return min(hits / max(total_checks, 1), 1.0), reasons


def _text_overlap_score(clause_text: str, reference_text: str) -> float:
    """Simple word-overlap similarity between two texts (Jaccard-like)."""
    def tokenize(t: str) -> set[str]:
        return {w.lower().strip(".,;:()[]") for w in t.split() if len(w) > 2}

    clause_words = tokenize(clause_text)
    ref_words = tokenize(reference_text)
    if not clause_words or not ref_words:
        return 0.0
    intersection = clause_words & ref_words
    union = clause_words | ref_words
    return len(intersection) / len(union)


async def _llm_semantic_score(
    clause_text: str,
    reference_text: str,
    clause_type: str,
    llm: Any,
) -> tuple[float, str]:
    """Use the LLM to semantically compare a clause to its reference and score deviation."""
    prompt = (
        f"You are a Hong Kong legal contract reviewer. "
        f"Compare the following extracted clause against the reference standard clause.\n\n"
        f"Clause type: {clause_type}\n\n"
        f"Extracted clause:\n{clause_text[:1500]}\n\n"
        f"Reference standard:\n{reference_text[:1500]}\n\n"
        f"Rate the deviation from 0.0 (identical/standard) to 1.0 (highly anomalous/risky).\n"
        f"Respond in this exact format:\n"
        f"SCORE: <number>\n"
        f"REASON: <one-sentence explanation>"
    )
    try:
        response = await llm.generate(prompt, max_tokens=120)
        score_match = re.search(r"SCORE:\s*([\d.]+)", response)
        reason_match = re.search(r"REASON:\s*(.+)", response)
        score = float(score_match.group(1)) if score_match else 0.5
        score = max(0.0, min(score, 1.0))
        reason = reason_match.group(1).strip() if reason_match else "LLM flagged deviation"
        return score, reason
    except Exception:
        logger.warning("LLM anomaly scoring failed, using keyword fallback")
        return 0.5, "Unable to perform semantic comparison"


def _find_matching_references(
    clause_type: str,
    reference_clauses: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Find reference clauses matching the given clause type."""
    return [
        rc for rc in reference_clauses
        if rc.get("clause_type") == clause_type
    ]


async def detect_anomalies(
    clauses: list[dict[str, Any]],
    reference_clauses: list[dict[str, Any]],
    llm: Any = None,
) -> list[dict[str, Any]]:
    """Compare extracted clauses against references and score deviations.

    Returns a list of dicts with keys:
        clause_number, clause_type, anomaly_score (0.0-1.0), flag_reason, text_content
    """
    results: list[dict[str, Any]] = []

    for clause in clauses:
        clause_type = clause.get("clause_type", "general")
        clause_text = clause.get("text_content", "")
        clause_number = clause.get("clause_number", "?")

        refs = _find_matching_references(clause_type, reference_clauses)

        keyword_score, keyword_reasons = _keyword_deviation_score(clause_text, clause_type)

        if refs:
            best_ref = refs[0]
            ref_text = best_ref.get("standard_text", "")
            overlap = _text_overlap_score(clause_text, ref_text)
            text_deviation = 1.0 - overlap

            if llm is not None:
                llm_score, llm_reason = await _llm_semantic_score(
                    clause_text, ref_text, clause_type, llm,
                )
                combined_score = (keyword_score * 0.3) + (text_deviation * 0.2) + (llm_score * 0.5)
                all_reasons = keyword_reasons + [llm_reason]
            else:
                combined_score = (keyword_score * 0.5) + (text_deviation * 0.5)
                all_reasons = keyword_reasons
                if text_deviation > 0.6:
                    all_reasons.append("Significant textual deviation from reference standard")

        else:
            if llm is not None and clause_type != "general":
                llm_score, llm_reason = await _llm_semantic_score(
                    clause_text, "", clause_type, llm,
                )
                combined_score = (keyword_score * 0.5) + (llm_score * 0.5)
                all_reasons = keyword_reasons + [llm_reason]
            else:
                combined_score = keyword_score
                all_reasons = keyword_reasons

            if not all_reasons and clause_type != "general":
                all_reasons.append("No reference template available for comparison")

        combined_score = max(0.0, min(round(combined_score, 2), 1.0))
        flag_reason = "; ".join(r for r in all_reasons if r) if all_reasons else None

        results.append({
            "clause_number": clause_number,
            "clause_type": clause_type,
            "anomaly_score": combined_score,
            "flag_reason": flag_reason,
            "text_content": clause_text,
        })

    return results
