"""Tests for document completeness validation."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from immigration.visa_doc_ocr.validators.completeness import check_document_completeness
from immigration.visa_doc_ocr.validators.expiry import check_document_expiry


class TestCompleteness:
    """Completeness checks per prompt testing criteria."""

    def test_gep_all_docs_present(self):
        docs = [
            {"doc_type": "passport", "status": "processed"},
            {"doc_type": "employment_contract", "status": "processed"},
            {"doc_type": "bank_statement", "status": "processed"},
            {"doc_type": "tax_return", "status": "processed"},
            {"doc_type": "degree_certificate", "status": "processed"},
            {"doc_type": "employer_br", "status": "processed"},
            {"doc_type": "company_profile", "status": "processed"},
            {"doc_type": "job_description", "status": "processed"},
            {"doc_type": "salary_proof", "status": "processed"},
        ]
        result = check_document_completeness("GEP", docs)
        assert result["completeness_pct"] == 100.0
        assert len(result["missing_docs"]) == 0

    def test_gep_missing_docs(self):
        docs = [
            {"doc_type": "passport", "status": "processed"},
            {"doc_type": "employment_contract", "status": "processed"},
        ]
        result = check_document_completeness("GEP", docs)
        assert result["completeness_pct"] < 100.0
        assert len(result["missing_docs"]) > 0

    def test_qmas_checklist(self):
        docs = []
        result = check_document_completeness("QMAS", docs)
        assert result["completeness_pct"] == 0.0
        assert len(result["required_docs"]) > 0

    def test_unknown_scheme(self):
        result = check_document_completeness("NONEXISTENT", [])
        assert "required_docs" in result


class TestExpiry:
    """Document expiry checks per prompt criteria."""

    def test_stale_bank_statement(self):
        from datetime import date, timedelta
        old_date = (date.today() - timedelta(days=120)).isoformat()
        docs = [{"doc_type": "bank_statement", "issue_date": old_date, "expiry_date": None}]
        flags = check_document_expiry(docs)
        assert len(flags) > 0
        assert any(f.get("flag_type") == "stale" for f in flags)

    def test_recent_bank_statement_ok(self):
        from datetime import date, timedelta
        recent_date = (date.today() - timedelta(days=30)).isoformat()
        docs = [{"doc_type": "bank_statement", "issue_date": recent_date, "expiry_date": None}]
        flags = check_document_expiry(docs)
        stale_flags = [f for f in flags if "bank" in f.get("doc_type", "").lower()]
        assert len(stale_flags) == 0

    def test_expired_passport(self):
        from datetime import date, timedelta
        past_date = (date.today() - timedelta(days=30)).isoformat()
        docs = [{"doc_type": "passport", "issue_date": None, "expiry_date": past_date}]
        flags = check_document_expiry(docs)
        assert len(flags) > 0
