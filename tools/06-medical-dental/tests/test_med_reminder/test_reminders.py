"""Tests for reminder message templates and compliance window logic."""

from datetime import datetime, timedelta

from openclaw_shared.database import get_db
from medical_dental.med_reminder.bot.message_templates import reminder_message
from medical_dental.med_reminder.reminders.compliance_tracker import (
    COMPLIANCE_WINDOW_HOURS,
    ComplianceTracker,
)


def test_message_template_en():
    msg = reminder_message(
        med_name_en="Amlodipine",
        med_name_tc="氨氯地平",
        dosage="5mg",
        frequency="once daily",
        language="en",
    )
    assert "Medication Reminder" in msg
    assert "Amlodipine" in msg
    assert "氨氯地平" in msg
    assert "5mg" in msg
    assert "once daily" in msg
    assert "taken" in msg.lower()


def test_message_template_tc():
    msg = reminder_message(
        med_name_en="Amlodipine",
        med_name_tc="氨氯地平",
        dosage="5mg",
        frequency="每日一次",
        language="tc",
    )
    assert "食藥提醒" in msg
    assert "氨氯地平" in msg
    assert "Amlodipine" in msg
    assert "5mg" in msg
    assert "每日一次" in msg
    assert "已服" in msg


def test_compliance_window_taken(db_paths):
    db = db_paths["med_reminder"]
    tracker = ComplianceTracker()

    with get_db(db) as conn:
        conn.execute(
            "INSERT INTO patients (name_en, phone) VALUES (?, ?)",
            ("Window Test", "+85200001111"),
        )
        patient_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.execute(
            """INSERT INTO medications
               (patient_id, drug_name_en, dosage, frequency, active)
               VALUES (?, ?, ?, ?, ?)""",
            (patient_id, "TestDrug", "10mg", "once daily", True),
        )
        med_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

        sent_time = datetime.now().isoformat()
        conn.execute(
            """INSERT INTO compliance_logs
               (patient_id, medication_id, reminder_sent_at)
               VALUES (?, ?, ?)""",
            (patient_id, med_id, sent_time),
        )

    log_id = tracker.record_taken(db, patient_id, med_id)
    assert log_id > 0

    with get_db(db) as conn:
        row = conn.execute(
            "SELECT * FROM compliance_logs WHERE id = ?", (log_id,)
        ).fetchone()
    assert row["taken"] == 1
    assert row["response"] == "taken"


def test_compliance_window_missed(db_paths):
    db = db_paths["med_reminder"]
    tracker = ComplianceTracker()

    with get_db(db) as conn:
        conn.execute(
            "INSERT INTO patients (name_en, phone) VALUES (?, ?)",
            ("Missed Test", "+85200002222"),
        )
        patient_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.execute(
            """INSERT INTO medications
               (patient_id, drug_name_en, dosage, frequency, active)
               VALUES (?, ?, ?, ?, ?)""",
            (patient_id, "TestDrug2", "5mg", "twice daily", True),
        )
        med_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    old_time = (datetime.now() - timedelta(hours=COMPLIANCE_WINDOW_HOURS + 1)).isoformat()
    log_id = tracker.record_missed(db, patient_id, med_id, old_time)
    assert log_id > 0

    with get_db(db) as conn:
        row = conn.execute(
            "SELECT * FROM compliance_logs WHERE id = ?", (log_id,)
        ).fetchone()
    assert row["taken"] == 0
    assert row["response"] == "missed"
