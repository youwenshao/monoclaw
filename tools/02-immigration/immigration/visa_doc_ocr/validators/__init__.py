"""Document validators: scheme requirements, completeness, and expiry checks."""

from immigration.visa_doc_ocr.validators.schemes import SCHEME_REQUIREMENTS, SCHEME_LABELS
from immigration.visa_doc_ocr.validators.completeness import check_document_completeness
from immigration.visa_doc_ocr.validators.expiry import check_document_expiry

__all__ = [
    "SCHEME_REQUIREMENTS",
    "SCHEME_LABELS",
    "check_document_completeness",
    "check_document_expiry",
]
