"""Tests for compliance tracking and escalation reporting."""

from datetime import datetime, timedelta

from openclaw_shared.database import get_db
from medical_dental.med_reminder.reminders.compliance_tracker import ComplianceTracker
from medical_dental.med_reminder.reminders.escalation import EscalationManager


def _setup_patient_with_meds(db_path):
    with get_db(db_path) as conn:
        conn.execute(
            "INSERT INTO patients (name_en, name_tc, phone) VALUES (?, ?, ?)",
            ("Compliance Patient", "依從病人", "+85200005555"),
        )
        patient_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.execute(
            """INSERT INTO medications
               (patient_id, drug_name_en, drug_name_tc, dosage, frequency, active)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (patient_id, "Metformin", "二甲雙胍", "500mg", "twice daily", True),
        )
        med_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    return patient_id, med_id


def test_record_taken(db_paths):
    db = db_paths["med_reminder"]
    tracker = ComplianceTracker()
    patient_id, med_id = _setup_patient_with_meds(db)

    log_id = tracker.record_taken(db, patient_id, med_id)
    assert log_id > 0

    with get_db(db) as conn:
        row = conn.execute(
            "SELECT * FROM compliance_logs WHERE id = ?", (log_id,)
        ).fetchone()
    assert row["taken"] == 1
    assert row["patient_id"] == patient_id
    assert row["medication_id"] == med_id


def test_patient_compliance_rate(db_paths):
    db = db_paths["med_reminder"]
    tracker = ComplianceTracker()
    patient_id, med_id = _setup_patient_with_meds(db)

    now = datetime.now()
    with get_db(db) as conn:
        for i in range(8):
            sent_time = (now - timedelta(days=i)).isoformat()
            conn.execute(
                """INSERT INTO compliance_logs
                   (patient_id, medication_id, reminder_sent_at, taken, response, responded_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (patient_id, med_id, sent_time, 1, "taken", sent_time),
            )
        for i in range(8, 10):
            sent_time = (now - timedelta(days=i)).isoformat()
            conn.execute(
                """INSERT INTO compliance_logs
                   (patient_id, medication_id, reminder_sent_at, taken, response)
                   VALUES (?, ?, ?, ?, ?)""",
                (patient_id, med_id, sent_time, 0, "missed"),
            )

    result = tracker.get_patient_compliance(db, patient_id, days=30)
    assert result["patient_id"] == patient_id
    assert len(result["medications"]) >= 1

    med_report = result["medications"][0]
    assert med_report["taken"] == 8
    assert med_report["missed"] == 2
    assert med_report["rate"] == 80.0
    assert result["overall_rate"] == 80.0


def test_low_compliance_patients(db_paths):
    db = db_paths["med_reminder"]
    tracker = ComplianceTracker()

    with get_db(db) as conn:
        conn.execute(
            "INSERT INTO patients (name_en, name_tc, phone) VALUES (?, ?, ?)",
            ("Low Compliance", "低依從", "+85200006666"),
        )
        patient_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.execute(
            """INSERT INTO medications
               (patient_id, drug_name_en, dosage, frequency, active)
               VALUES (?, ?, ?, ?, ?)""",
            (patient_id, "DrugX", "10mg", "once daily", True),
        )
        med_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

        now = datetime.now()
        for i in range(2):
            t = (now - timedelta(days=i)).isoformat()
            conn.execute(
                """INSERT INTO compliance_logs
                   (patient_id, medication_id, reminder_sent_at, taken, response, responded_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (patient_id, med_id, t, 1, "taken", t),
            )
        for i in range(2, 10):
            t = (now - timedelta(days=i)).isoformat()
            conn.execute(
                """INSERT INTO compliance_logs
                   (patient_id, medication_id, reminder_sent_at, taken, response)
                   VALUES (?, ?, ?, ?, ?)""",
                (patient_id, med_id, t, 0, "missed"),
            )

    flagged = tracker.get_low_compliance_patients(db, threshold=60)
    matching = [p for p in flagged if p["patient_id"] == patient_id]
    assert len(matching) == 1
    assert matching[0]["compliance_rate"] < 60


def test_escalation_report(db_paths):
    db = db_paths["med_reminder"]
    escalation = EscalationManager()

    with get_db(db) as conn:
        conn.execute(
            "INSERT INTO patients (name_en, name_tc, phone, preferred_language) VALUES (?, ?, ?, ?)",
            ("Report Patient", "報告病人", "+85200007777", "en"),
        )
        patient_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.execute(
            """INSERT INTO medications
               (patient_id, drug_name_en, drug_name_tc, dosage, frequency, active)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (patient_id, "ReportDrug", "報告藥", "10mg", "once daily", True),
        )

    report = escalation.generate_escalation_report(db, patient_id)

    assert "patient" in report
    assert report["patient"]["id"] == patient_id
    assert report["patient"]["name_en"] == "Report Patient"
    assert "medications" in report
    assert "compliance" in report
    assert "trend" in report
    assert report["trend"] in ("improving", "declining", "stable")
    assert "generated_at" in report
