"""Structured data extraction from papers during systematic review."""

from __future__ import annotations

import json
import logging
from typing import Any

from openclaw_shared.database import get_db

logger = logging.getLogger("openclaw.academic.paper_sieve.data_extraction")

_DEFAULT_TEMPLATES: dict[str, dict[str, Any]] = {
    "general": {
        "fields": [
            {"name": "study_design", "type": "text", "description": "Type of study design"},
            {"name": "sample_size", "type": "number", "description": "Number of participants or observations"},
            {"name": "population", "type": "text", "description": "Study population characteristics"},
            {"name": "intervention", "type": "text", "description": "Intervention or exposure studied"},
            {"name": "comparator", "type": "text", "description": "Control or comparator group"},
            {"name": "outcome_measures", "type": "text", "description": "Primary and secondary outcome measures"},
            {"name": "key_findings", "type": "text", "description": "Main results and findings"},
            {"name": "limitations", "type": "text", "description": "Study limitations noted by authors"},
            {"name": "funding_source", "type": "text", "description": "Funding source if reported"},
        ],
    },
    "rct": {
        "fields": [
            {"name": "study_design", "type": "text", "description": "RCT design (parallel, crossover, cluster)"},
            {"name": "randomisation_method", "type": "text", "description": "Randomisation method"},
            {"name": "blinding", "type": "text", "description": "Blinding level (single, double, open-label)"},
            {"name": "sample_size", "type": "number", "description": "Total participants randomised"},
            {"name": "population", "type": "text", "description": "Eligibility criteria"},
            {"name": "intervention", "type": "text", "description": "Intervention details"},
            {"name": "comparator", "type": "text", "description": "Control group details"},
            {"name": "primary_outcome", "type": "text", "description": "Primary outcome measure"},
            {"name": "secondary_outcomes", "type": "text", "description": "Secondary outcome measures"},
            {"name": "effect_size", "type": "text", "description": "Effect size and confidence interval"},
            {"name": "adverse_events", "type": "text", "description": "Adverse events reported"},
            {"name": "risk_of_bias", "type": "text", "description": "Risk of bias assessment"},
        ],
    },
}


def extract_data_from_paper(
    db_path: str,
    review_id: int,
    paper_id: int,
    template: dict[str, Any],
    llm: Any,
) -> dict[str, Any]:
    """Extract structured data from a paper's chunks using an LLM.

    *template* defines the fields to extract (see ``get_extraction_template``).
    Returns the extracted data dict keyed by field name.
    """
    with get_db(db_path) as conn:
        paper = conn.execute(
            "SELECT title, authors, abstract FROM papers WHERE id = ?",
            (paper_id,),
        ).fetchone()
        chunks = conn.execute(
            "SELECT text_content, section_name, page_number "
            "FROM chunks WHERE paper_id = ? ORDER BY chunk_index",
            (paper_id,),
        ).fetchall()

    if not paper:
        logger.warning("Paper id=%d not found", paper_id)
        return {}

    full_text = "\n\n".join(
        f"[{row['section_name'] or 'body'}, p.{row['page_number'] or '?'}] {row['text_content']}"
        for row in chunks
    )

    field_descriptions = "\n".join(
        f"- {f['name']}: {f['description']} (type: {f['type']})"
        for f in template.get("fields", [])
    )

    prompt = (
        "You are extracting structured data from an academic paper for a systematic review.\n\n"
        f"Paper: {paper['title']} by {paper['authors']}\n"
        f"Abstract: {paper['abstract'] or 'N/A'}\n\n"
        f"Full text excerpts:\n{full_text[:6000]}\n\n"
        "Extract the following fields. Return ONLY a valid JSON object with these keys:\n"
        f"{field_descriptions}\n\n"
        "If a field cannot be determined from the text, use null. "
        "Respond with the JSON object only, no explanation."
    )

    raw = llm.generate(prompt).strip()

    try:
        extracted = json.loads(raw)
    except json.JSONDecodeError:
        start = raw.find("{")
        end = raw.rfind("}") + 1
        if start != -1 and end > start:
            try:
                extracted = json.loads(raw[start:end])
            except json.JSONDecodeError:
                logger.error("Failed to parse extraction output for paper %d", paper_id)
                extracted = {"_raw": raw[:1000], "_error": "parse_failure"}
        else:
            extracted = {"_raw": raw[:1000], "_error": "parse_failure"}

    save_extracted_data(db_path, review_id, paper_id, extracted)
    return extracted


def get_extraction_template(review_type: str = "general") -> dict[str, Any]:
    """Return a default extraction template for the given review type.

    Supported types: 'general', 'rct'.  Falls back to 'general' for
    unrecognised types.
    """
    return _DEFAULT_TEMPLATES.get(review_type, _DEFAULT_TEMPLATES["general"])


def save_extracted_data(
    db_path: str,
    review_id: int,
    paper_id: int,
    data: dict[str, Any],
) -> bool:
    """Persist extracted data as JSON on the review_papers row.

    Returns True on success, False if the row was not found.
    """
    serialised = json.dumps(data, ensure_ascii=False)
    with get_db(db_path) as conn:
        cursor = conn.execute(
            "UPDATE review_papers SET extracted_data = ? "
            "WHERE review_id = ? AND paper_id = ?",
            (serialised, review_id, paper_id),
        )
        updated = cursor.rowcount > 0

    if updated:
        logger.info("Saved extraction data for paper %d in review %d", paper_id, review_id)
    return updated
