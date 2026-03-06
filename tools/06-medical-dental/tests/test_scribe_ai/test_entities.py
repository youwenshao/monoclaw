"""Tests for note manager, finalization, and template engine."""

from openclaw_shared.database import get_db
from medical_dental.scribe_ai.records.note_manager import NoteManager
from medical_dental.scribe_ai.records.finalization import Finalization
from medical_dental.scribe_ai.records.template_engine import TemplateEngine


def _create_patient(db_path):
    with get_db(db_path) as conn:
        conn.execute(
            "INSERT INTO patients (patient_ref, name_en, gender) VALUES (?, ?, ?)",
            ("P-TEST-001", "Test Patient", "M"),
        )
        return conn.execute("SELECT last_insert_rowid()").fetchone()[0]


def test_note_manager_crud(db_paths):
    db = db_paths["scribe_ai"]
    mgr = NoteManager()
    patient_id = _create_patient(db)

    note_id = mgr.create_note(
        db,
        patient_id=patient_id,
        doctor="Dr. Test",
        soap_data={
            "subjective": "Sore throat",
            "objective": "Temp 37.5",
            "assessment": "URTI",
            "plan": "Rest and fluids",
        },
        icd10_codes=["J06.9"],
    )
    assert note_id > 0

    note = mgr.get_note(db, note_id)
    assert note is not None
    assert note["soap_subjective"] == "Sore throat"
    assert note["soap_assessment"] == "URTI"
    assert note["icd10_codes"] == ["J06.9"]
    assert note["status"] == "draft"

    updated = mgr.update_note(db, note_id, soap_plan="Paracetamol 500mg QID")
    assert updated is True

    note = mgr.get_note(db, note_id)
    assert note["soap_plan"] == "Paracetamol 500mg QID"


def test_finalization_locks_note(db_paths):
    db = db_paths["scribe_ai"]
    mgr = NoteManager()
    fin = Finalization()
    patient_id = _create_patient(db)

    note_id = mgr.create_note(
        db,
        patient_id=patient_id,
        doctor="Dr. Test",
        soap_data={
            "subjective": "Headache",
            "objective": "BP 140/90",
            "assessment": "Hypertension",
            "plan": "Amlodipine 5mg",
        },
    )

    result = fin.finalize_note(db, note_id, "Dr. Test")
    assert result is True

    note = mgr.get_note(db, note_id)
    assert note["status"] == "finalized"
    assert note["finalized_by"] == "Dr. Test"

    updated = mgr.update_note(db, note_id, soap_plan="Changed plan")
    assert updated is False


def test_amendment_creates_new_record(db_paths):
    db = db_paths["scribe_ai"]
    mgr = NoteManager()
    fin = Finalization()
    patient_id = _create_patient(db)

    original_id = mgr.create_note(
        db,
        patient_id=patient_id,
        doctor="Dr. Test",
        soap_data={
            "subjective": "Cough",
            "objective": "Lungs clear",
            "assessment": "Viral URTI",
            "plan": "Symptomatic relief",
        },
        icd10_codes=["J06.9"],
    )
    fin.finalize_note(db, original_id, "Dr. Test")

    amendment_id = fin.amend_note(
        db,
        original_id,
        amended_by="Dr. Senior",
        soap_data={"plan": "Symptomatic relief. Add Dextromethorphan."},
        icd10_codes=["J06.9", "R05"],
    )
    assert amendment_id != original_id

    amendment = mgr.get_note(db, amendment_id)
    assert amendment["amendment_of"] == original_id
    assert amendment["status"] == "draft"
    assert amendment["doctor"] == "Dr. Senior"

    original = mgr.get_note(db, original_id)
    assert original["status"] == "finalized"


def test_template_engine_apply(seeded_db_paths):
    db = seeded_db_paths["scribe_ai"]
    engine = TemplateEngine()

    templates = engine.get_templates(db)
    assert len(templates) > 0

    urti_templates = [t for t in templates if t["name"] == "URTI"]
    assert len(urti_templates) == 1
    template = urti_templates[0]

    result = engine.apply_template(
        template,
        overrides={
            "subjective": "Sore throat and cough for 2 days",
            "objective": "Temp 37.8°C, BP 120/80. Pharynx red.",
        },
    )

    assert result["subjective"] == "Sore throat and cough for 2 days"
    assert result["objective"] == "Temp 37.8°C, BP 120/80. Pharynx red."
    assert "assessment" in result
    assert "plan" in result
