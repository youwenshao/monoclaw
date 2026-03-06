"""NDA clause completeness checker for non-disclosure agreements."""

from __future__ import annotations

from typing import Any

NDA_REQUIRED_ELEMENTS: list[dict[str, Any]] = [
    {
        "element": "scope_of_confidential_information",
        "name": "Scope of confidential information",
        "description": "Definition of what constitutes confidential information",
        "keywords": [
            "confidential information means", "confidential information includes",
            "definition of confidential", "scope of confidential",
            "shall mean all information", "proprietary information",
            "trade secrets", "all information disclosed",
        ],
    },
    {
        "element": "exclusions",
        "name": "Exclusions from confidentiality",
        "description": "Carve-outs for publicly available info, independently developed info, etc.",
        "keywords": [
            "shall not include", "does not include", "exclusion",
            "publicly available", "public domain", "independently developed",
            "independently acquired", "already known", "prior knowledge",
            "received from a third party", "not confidential",
        ],
    },
    {
        "element": "permitted_disclosures",
        "name": "Permitted disclosures",
        "description": "Circumstances where disclosure is allowed (including SFC-mandated for HK)",
        "keywords": [
            "permitted disclos", "authorised disclos", "authorized disclos",
            "may disclose", "entitled to disclose",
            "compelled by law", "required by law", "court order", "subpoena",
            "regulatory authority", "SFC", "Securities and Futures Commission",
            "HKMA", "statutory requirement", "legal obligation",
        ],
    },
    {
        "element": "duration",
        "name": "Duration of obligations",
        "description": "Time period for which confidentiality obligations apply",
        "keywords": [
            "duration", "term of", "period of", "survive for",
            "shall continue", "remain in effect", "obligations shall last",
            "expiry", "termination of this agreement",
            "years from", "months from",
        ],
    },
    {
        "element": "return_obligations",
        "name": "Return/destruction obligations",
        "description": "Requirement to return or destroy confidential materials upon termination",
        "keywords": [
            "return of", "return all", "return obligations",
            "destruction of", "destroy all", "deliver up",
            "promptly return", "shall return",
            "certify destruction", "certificate of destruction",
            "delete all copies", "erase",
        ],
    },
    {
        "element": "governing_law",
        "name": "Governing law",
        "description": "Applicable law and jurisdiction clause",
        "keywords": [
            "governing law", "governed by", "applicable law",
            "laws of hong kong", "HKSAR", "jurisdiction",
            "courts of hong kong", "exclusive jurisdiction",
            "non-exclusive jurisdiction",
        ],
    },
]


def _find_matching_clauses(
    clauses: list[dict[str, Any]],
    keywords: list[str],
) -> list[dict[str, Any]]:
    """Find clauses containing any of the specified keywords."""
    matched = []
    for clause in clauses:
        text_lower = clause.get("text_content", "").lower()
        hits = [kw for kw in keywords if kw.lower() in text_lower]
        if hits:
            matched.append({
                **clause,
                "_matched_keywords": hits,
            })
    return matched


def _assess_scope_quality(matched_clauses: list[dict[str, Any]]) -> dict[str, Any]:
    """Assess whether scope definition is sufficiently broad or overly narrow."""
    if not matched_clauses:
        return {"quality": "missing", "note": "No scope definition found"}

    combined = " ".join(c.get("text_content", "") for c in matched_clauses).lower()

    broad_indicators = [
        "all information", "any information", "includes but is not limited to",
        "whether oral, written", "in any form",
    ]
    narrow_indicators = [
        "limited to", "only includes", "specifically means",
    ]

    broad_count = sum(1 for ind in broad_indicators if ind in combined)
    narrow_count = sum(1 for ind in narrow_indicators if ind in combined)

    if broad_count >= 2:
        return {"quality": "comprehensive", "note": "Scope is broadly defined"}
    if narrow_count > broad_count:
        return {"quality": "narrow", "note": "Scope may be too narrowly defined"}
    return {"quality": "adequate", "note": "Scope definition present"}


def _assess_sfc_compliance(matched_clauses: list[dict[str, Any]]) -> dict[str, Any]:
    """Check whether permitted disclosures include SFC-mandated disclosures (HK-specific)."""
    if not matched_clauses:
        return {"sfc_compliant": False, "note": "No permitted disclosure clause found"}

    combined = " ".join(c.get("text_content", "") for c in matched_clauses).lower()

    sfc_terms = [
        "sfc", "securities and futures commission", "securities and futures ordinance",
        "regulatory authority", "hkma", "hong kong monetary authority",
    ]
    has_sfc = any(term in combined for term in sfc_terms)

    regulatory_terms = [
        "required by law", "compelled by law", "statutory requirement",
        "regulatory requirement", "legal obligation",
    ]
    has_regulatory = any(term in combined for term in regulatory_terms)

    if has_sfc:
        return {"sfc_compliant": True, "note": "Explicitly references SFC/regulatory disclosure"}
    if has_regulatory:
        return {
            "sfc_compliant": True,
            "note": "General regulatory disclosure carve-out (covers SFC implicitly)",
        }
    return {
        "sfc_compliant": False,
        "note": "No regulatory or SFC disclosure carve-out found; may conflict with HK regulatory requirements",
    }


def check_nda_completeness(clauses: list[dict[str, Any]]) -> dict[str, Any]:
    """Check NDA clause completeness against required elements.

    Returns a dict with:
        complete: bool (all required elements present)
        elements: list of per-element check results
        summary: human-readable summary
        sfc_compliance: HK SFC-specific assessment
    """
    elements: list[dict[str, Any]] = []
    all_present = True

    for req in NDA_REQUIRED_ELEMENTS:
        matched = _find_matching_clauses(clauses, req["keywords"])
        present = len(matched) > 0

        entry = {
            "element": req["element"],
            "name": req["name"],
            "description": req["description"],
            "present": present,
            "matched_clauses": [c.get("clause_number", "?") for c in matched],
        }

        if req["element"] == "scope_of_confidential_information" and present:
            quality = _assess_scope_quality(matched)
            entry["quality_assessment"] = quality

        elements.append(entry)

        if not present:
            all_present = False

    permitted_clauses = _find_matching_clauses(
        clauses,
        NDA_REQUIRED_ELEMENTS[2]["keywords"],
    )
    sfc_assessment = _assess_sfc_compliance(permitted_clauses)

    present_items = [e for e in elements if e["present"]]
    missing_items = [e for e in elements if not e["present"]]

    summary_parts = [f"{len(present_items)}/{len(elements)} required elements present"]
    if missing_items:
        missing_names = ", ".join(e["name"] for e in missing_items)
        summary_parts.append(f"Missing: {missing_names}")
    if not sfc_assessment["sfc_compliant"]:
        summary_parts.append("SFC disclosure carve-out may be insufficient")

    return {
        "complete": all_present,
        "elements": elements,
        "summary": "; ".join(summary_parts),
        "sfc_compliance": sfc_assessment,
    }
