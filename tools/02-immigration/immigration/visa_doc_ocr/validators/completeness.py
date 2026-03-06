"""Document completeness checker for immigration scheme applications."""

from __future__ import annotations

from typing import Any

from immigration.visa_doc_ocr.validators.schemes import SCHEME_REQUIREMENTS, SCHEME_LABELS


def check_document_completeness(scheme: str, documents: list[dict[str, Any]]) -> dict[str, Any]:
    """Check whether all required documents for a scheme have been submitted.

    Args:
        scheme: Immigration scheme code (e.g. "GEP", "QMAS").
        documents: List of document dicts, each must have a "doc_type" key.

    Returns dict with: scheme, scheme_label, required_docs, submitted_docs,
    missing_docs, completeness_pct.
    """
    required = SCHEME_REQUIREMENTS.get(scheme, [])
    submitted_types = {doc.get("doc_type") for doc in documents if doc.get("doc_type")}

    submitted = sorted(submitted_types & set(required))
    missing = sorted(set(required) - submitted_types)

    pct = (len(submitted) / len(required) * 100) if required else 100.0

    return {
        "scheme": scheme,
        "scheme_label": SCHEME_LABELS.get(scheme, scheme),
        "required_docs": required,
        "submitted_docs": submitted,
        "missing_docs": missing,
        "completeness_pct": round(pct, 1),
    }
