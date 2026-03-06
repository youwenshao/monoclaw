"""Tests for refill workflow, drug interactions, and drug matcher."""

import pytest

from openclaw_shared.database import get_db
from medical_dental.med_reminder.refill.refill_workflow import RefillWorkflow
from medical_dental.med_reminder.safety.interaction_checker import InteractionChecker
from medical_dental.med_reminder.refill.drug_matcher import DrugMatcher


def _setup_patient_and_med(db_path, drug_en="TestRefillDrug", drug_tc="測試補藥"):
    with get_db(db_path) as conn:
        conn.execute(
            "INSERT INTO patients (name_en, phone) VALUES (?, ?)",
            ("Refill Patient", "+85200008888"),
        )
        patient_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.execute(
            """INSERT INTO medications
               (patient_id, drug_name_en, drug_name_tc, dosage, frequency, refill_eligible, active)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (patient_id, drug_en, drug_tc, "10mg", "once daily", True, True),
        )
        med_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    return patient_id, med_id


def test_create_refill_request(db_paths):
    db = db_paths["med_reminder"]
    workflow = RefillWorkflow()
    patient_id, med_id = _setup_patient_and_med(db)

    request_id = workflow.create_request(db, patient_id, med_id)
    assert request_id > 0

    with get_db(db) as conn:
        row = conn.execute(
            "SELECT * FROM refill_requests WHERE id = ?", (request_id,)
        ).fetchone()
    assert row["status"] == "pending"
    assert row["patient_id"] == patient_id
    assert row["medication_id"] == med_id


def test_refill_status_transitions(db_paths):
    db = db_paths["med_reminder"]
    workflow = RefillWorkflow()
    patient_id, med_id = _setup_patient_and_med(db)

    req_id = workflow.create_request(db, patient_id, med_id)

    assert workflow.approve_request(db, req_id, "Dr. Approver") is True
    with get_db(db) as conn:
        row = conn.execute("SELECT status FROM refill_requests WHERE id = ?", (req_id,)).fetchone()
    assert row["status"] == "approved"

    assert workflow.mark_ready(db, req_id) is True
    with get_db(db) as conn:
        row = conn.execute("SELECT status FROM refill_requests WHERE id = ?", (req_id,)).fetchone()
    assert row["status"] == "ready"

    assert workflow.mark_collected(db, req_id) is True
    with get_db(db) as conn:
        row = conn.execute("SELECT status FROM refill_requests WHERE id = ?", (req_id,)).fetchone()
    assert row["status"] == "collected"


def test_invalid_refill_transition(db_paths):
    db = db_paths["med_reminder"]
    workflow = RefillWorkflow()
    patient_id, med_id = _setup_patient_and_med(db)

    req_id = workflow.create_request(db, patient_id, med_id)

    result = workflow.mark_ready(db, req_id)
    assert result is False

    result = workflow.mark_collected(db, req_id)
    assert result is False


def test_drug_interaction_check(seeded_db_paths):
    db = seeded_db_paths["med_reminder"]
    checker = InteractionChecker()

    result = checker.check_pair(db, "Warfarin", "Aspirin")
    assert result is not None
    assert result["severity"] == "major"
    assert "bleeding" in result["description"].lower()


def test_drug_matcher_fuzzy(seeded_db_paths):
    db = seeded_db_paths["med_reminder"]
    matcher = DrugMatcher()

    result = matcher.match("Amlodipne", db)
    assert result["drug_name_en"] is not None
    assert result["drug_name_en"] == "Amlodipine"
    assert result["confidence"] > 0.4
    assert result["medication_id"] is not None


def test_no_interaction_for_safe_pair(seeded_db_paths):
    db = seeded_db_paths["med_reminder"]
    checker = InteractionChecker()

    result = checker.check_pair(db, "Amlodipine", "Metformin")
    assert result is None
