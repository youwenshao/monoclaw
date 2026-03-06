"""Clause extraction engine — regex boundary detection with LLM classification."""

from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger("openclaw.legal.doc_analyzer.clause_extractor")

CLAUSE_HEADING_RE = re.compile(
    r"^"
    r"(?:"
    r"(?P<numbered>\d+(?:\.\d+)*)\s*\.?\s+"       # "1.", "3.2", "12.1.3"
    r"|(?P<schedule>SCHEDULE\s+\w+)"               # "SCHEDULE A"
    r"|(?P<article>ARTICLE\s+\w+)"                 # "ARTICLE IV"
    r"|(?P<part>PART\s+\w+)"                        # "PART II"
    r"|(?P<recital>RECITAL\w*)"                     # "RECITALS"
    r"|(?P<annex>ANNEX\s+\w+)"                      # "ANNEX 1"
    r"|(?P<appendix>APPENDIX\s+\w+)"                # "APPENDIX A"
    r"|(?P<alpha>\([a-z]\))\s+"                     # "(a) ..."
    r")",
    re.IGNORECASE | re.MULTILINE,
)

CLAUSE_TYPE_KEYWORDS: dict[str, list[str]] = {
    "termination": [
        "terminat", "notice period", "expir", "cessation", "end of term",
    ],
    "indemnity": [
        "indemnif", "indemnity", "hold harmless", "compensat",
    ],
    "liability_cap": [
        "liability", "limit of liability", "aggregate liability", "cap on",
        "maximum liability", "exclusion of liability",
    ],
    "rent_review": [
        "rent review", "rent adjustment", "rent escalat", "rent increase",
        "market rent",
    ],
    "non_compete": [
        "non-compet", "non compet", "restraint of trade", "restrictive covenant",
        "competing business",
    ],
    "confidentiality": [
        "confidential", "non-disclosure", "nda", "proprietary information",
        "trade secret",
    ],
    "severance": [
        "severance", "redundancy", "long service payment",
    ],
    "wage_period": [
        "wage period", "payment of wages", "salary period", "remuneration",
    ],
    "annual_leave": [
        "annual leave", "paid leave", "vacation", "holiday entitlement",
    ],
    "statutory_holiday": [
        "statutory holiday", "public holiday", "general holiday",
    ],
    "governing_law": [
        "governing law", "jurisdiction", "applicable law", "laws of hong kong",
    ],
    "force_majeure": [
        "force majeure", "act of god", "unforeseeable",
    ],
    "dispute_resolution": [
        "arbitrat", "mediat", "dispute resolution", "HKIAC",
    ],
    "duration": [
        "duration", "term of agreement", "commencement date", "expiry date",
    ],
    "return_obligations": [
        "return of", "return obligations", "destruction of", "deliver up",
    ],
    "permitted_disclosure": [
        "permitted disclos", "authorised disclos", "SFC", "regulatory",
        "compelled by law", "court order",
    ],
    "exclusions": [
        "exclusion", "does not include", "shall not apply to",
        "publicly available", "independently developed",
    ],
    "scope_confidential": [
        "confidential information means", "definition of confidential",
        "scope of confidential",
    ],
}


def _classify_clause_by_keywords(text: str) -> str:
    """Score each clause type by keyword frequency; return the best match or 'general'."""
    text_lower = text.lower()
    best_type = "general"
    best_score = 0
    for clause_type, keywords in CLAUSE_TYPE_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw.lower() in text_lower)
        if score > best_score:
            best_score = score
            best_type = clause_type
    return best_type


async def _classify_clause_by_llm(
    text: str, contract_type: str, llm: Any,
) -> str:
    """Use the LLM to classify a single clause into a known type."""
    prompt = (
        f"You are a Hong Kong legal document analyst. "
        f"Classify the following clause from a {contract_type} contract into exactly one of these types: "
        f"termination, indemnity, liability_cap, rent_review, non_compete, confidentiality, "
        f"severance, wage_period, annual_leave, statutory_holiday, governing_law, "
        f"force_majeure, dispute_resolution, duration, return_obligations, "
        f"permitted_disclosure, exclusions, scope_confidential, general.\n\n"
        f"Respond with ONLY the type name, nothing else.\n\n"
        f"Clause text:\n{text[:2000]}"
    )
    try:
        response = await llm.generate(prompt, max_tokens=30)
        raw = response.strip().lower().replace(" ", "_")
        if raw in CLAUSE_TYPE_KEYWORDS or raw == "general":
            return raw
        return _classify_clause_by_keywords(text)
    except Exception:
        logger.warning("LLM classification failed, falling back to keywords")
        return _classify_clause_by_keywords(text)


def _split_into_raw_clauses(text: str) -> list[dict[str, Any]]:
    """Split document text into clause segments using regex heading detection."""
    matches = list(CLAUSE_HEADING_RE.finditer(text))

    if not matches:
        return [{
            "clause_number": "1",
            "text": text.strip(),
            "start_offset": 0,
            "end_offset": len(text),
        }]

    clauses: list[dict[str, Any]] = []

    if matches[0].start() > 0:
        preamble = text[:matches[0].start()].strip()
        if preamble:
            clauses.append({
                "clause_number": "preamble",
                "text": preamble,
                "start_offset": 0,
                "end_offset": matches[0].start(),
            })

    for i, match in enumerate(matches):
        start = match.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        clause_text = text[start:end].strip()

        clause_number = (
            match.group("numbered")
            or match.group("schedule")
            or match.group("article")
            or match.group("part")
            or match.group("recital")
            or match.group("annex")
            or match.group("appendix")
            or match.group("alpha")
            or str(i + 1)
        )

        clauses.append({
            "clause_number": clause_number.strip(),
            "text": clause_text,
            "start_offset": start,
            "end_offset": end,
        })

    return clauses


async def extract_clauses(
    text: str,
    contract_type: str,
    llm: Any = None,
) -> list[dict[str, Any]]:
    """Extract and classify clauses from contract text.

    Returns a list of dicts with keys:
        clause_number, clause_type, text_content, start_offset, end_offset
    """
    raw_clauses = _split_into_raw_clauses(text)
    results: list[dict[str, Any]] = []

    for raw in raw_clauses:
        clause_text = raw["text"]

        if llm is not None:
            clause_type = await _classify_clause_by_llm(
                clause_text, contract_type, llm,
            )
        else:
            clause_type = _classify_clause_by_keywords(clause_text)

        results.append({
            "clause_number": raw["clause_number"],
            "clause_type": clause_type,
            "text_content": clause_text,
            "start_offset": raw["start_offset"],
            "end_offset": raw["end_offset"],
        })

    return results
