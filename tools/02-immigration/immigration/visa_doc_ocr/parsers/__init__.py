"""Document parsers for HK immigration document types."""

from immigration.visa_doc_ocr.parsers.hkid import parse_hkid, validate_hkid
from immigration.visa_doc_ocr.parsers.passport import parse_passport, decode_mrz
from immigration.visa_doc_ocr.parsers.bank_statement import parse_bank_statement
from immigration.visa_doc_ocr.parsers.tax_return import parse_tax_return
from immigration.visa_doc_ocr.parsers.employment import parse_employment_contract

__all__ = [
    "parse_hkid",
    "validate_hkid",
    "parse_passport",
    "decode_mrz",
    "parse_bank_statement",
    "parse_tax_return",
    "parse_employment_contract",
]
