"""Tests for claim tracker and EOB parser."""

import asyncio
from datetime import date, timedelta

import pytest

from openclaw_shared.database import get_db
from medical_dental.insurance_agent.claims.claim_tracker import ClaimTracker
from medical_dental.insurance_agent.claims.eob_parser import EobParser


def test_create_claim(db_paths):
    tracker = ClaimTracker(db_paths["insurance_agent"])

    with get_db(db_paths["insurance_agent"]) as conn:
        conn.execute(
            "INSERT INTO patients (name_en, phone) VALUES (?, ?)",
            ("Test Patient", "+85200000001"),
        )
        patient_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    claim_id = tracker.create_claim({
        "patient_id": patient_id,
        "procedure_code": "GP001",
        "description": "GP consultation",
        "billed_amount": 500,
    })

    claim = tracker.get_by_id(claim_id)
    assert claim is not None
    assert claim["patient_id"] == patient_id
    assert claim["procedure_code"] == "GP001"
    assert claim["billed_amount"] == 500
    assert claim["status"] == "pending"


def test_claim_status_transitions(db_paths):
    tracker = ClaimTracker(db_paths["insurance_agent"])

    with get_db(db_paths["insurance_agent"]) as conn:
        conn.execute(
            "INSERT INTO patients (name_en, phone) VALUES (?, ?)",
            ("Transition Patient", "+85200000002"),
        )
        patient_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    claim_id = tracker.create_claim({
        "patient_id": patient_id,
        "billed_amount": 1000,
    })

    updated = tracker.update_claim(claim_id, status="submitted")
    assert updated["status"] == "submitted"

    updated = tracker.update_claim(claim_id, status="approved", approved_amount=800)
    assert updated["status"] == "approved"
    assert updated["approved_amount"] == 800

    updated = tracker.update_claim(claim_id, status="paid")
    assert updated["status"] == "paid"


def test_invalid_claim_transition(db_paths):
    tracker = ClaimTracker(db_paths["insurance_agent"])

    with get_db(db_paths["insurance_agent"]) as conn:
        conn.execute(
            "INSERT INTO patients (name_en, phone) VALUES (?, ?)",
            ("Invalid Transition", "+85200000003"),
        )
        patient_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    claim_id = tracker.create_claim({
        "patient_id": patient_id,
        "billed_amount": 500,
    })

    with pytest.raises(ValueError, match="Cannot transition"):
        tracker.update_claim(claim_id, status="approved")


def test_get_overdue_claims(db_paths):
    tracker = ClaimTracker(db_paths["insurance_agent"])

    with get_db(db_paths["insurance_agent"]) as conn:
        conn.execute(
            "INSERT INTO patients (name_en, phone) VALUES (?, ?)",
            ("Overdue Patient", "+85200000004"),
        )
        patient_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    claim_id = tracker.create_claim({
        "patient_id": patient_id,
        "billed_amount": 1200,
    })

    old_date = (date.today() - timedelta(days=45)).isoformat()
    with get_db(db_paths["insurance_agent"]) as conn:
        conn.execute(
            "UPDATE claims SET status = 'submitted', submitted_at = ? WHERE id = ?",
            (old_date, claim_id),
        )

    overdue = tracker.get_overdue(days=30)
    assert any(c["id"] == claim_id for c in overdue)


def test_eob_parser_text():
    parser = EobParser()
    sample_text = (
        "Explanation of Benefits\n"
        "Claim Ref: CLM-BUPA-20260301\n"
        "Billed Amount: HK$1,200.00\n"
        "Approved Amount: HK$960.00\n"
        "Patient Responsibility: HK$240.00\n"
        "Remarks: Co-insurance applied at 20%\n"
    )

    result = asyncio.run(parser.parse_text(sample_text))

    assert result["claim_reference"] == "CLM-BUPA-20260301"
    assert result["billed_amount"] == 1200.0
    assert result["approved_amount"] == 960.0
    assert result["patient_responsibility"] == 240.0
    assert "co-insurance" in result["remarks"].lower()
    assert result["source"] == "regex"
